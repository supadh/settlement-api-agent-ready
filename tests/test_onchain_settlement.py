from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

import main
import reconcile
from coinbase import CoinbaseTransferError
from feature_flags import FeatureFlags

client = TestClient(main.app)


class FakeCoinbaseClient:
    """Test double that records transfer attempts and returns a fixed hash."""

    def __init__(self, tx_hash: str = "0xtxhash") -> None:
        self.tx_hash = tx_hash
        self.error: Exception | None = None
        self.calls: list[tuple[str, int]] = []

    def send_usdc_transfer(self, destination_address: str, amount_units: int) -> str:
        self.calls.append((destination_address, amount_units))
        if self.error is not None:
            raise self.error
        return self.tx_hash


@pytest.fixture(autouse=True)
def isolate_onchain_idempotency() -> Generator[None, None, None]:
    main.onchain_settlements_by_idempotency_key.clear()
    yield
    main.onchain_settlements_by_idempotency_key.clear()


def _enable_onchain_settlement(
    monkeypatch: pytest.MonkeyPatch, fake_client: FakeCoinbaseClient
) -> None:
    monkeypatch.setattr(
        main, "feature_flags", FeatureFlags(onchain_settlement_enabled=True)
    )
    monkeypatch.setattr(main, "coinbase_client", fake_client)


def _create_charge(amount_cents: int) -> Any:
    response = client.post(
        "/charges",
        json={
            "merchant_id": "merchant-123",
            "amount_cents": amount_cents,
            "card_token": "card-token",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_happy_path_records_line_and_calls_coinbase_once(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeCoinbaseClient()
    _enable_onchain_settlement(monkeypatch, fake)
    charge = _create_charge(2500)

    with caplog.at_level("INFO"):
        response = client.post(
            "/settlements/onchain",
            json={
                "charge_id": charge["id"],
                "amount_cents": 2500,
                "destination_address": "0xwallet-address",
            },
            headers={"Idempotency-Key": "payout-1"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["charge_id"] == charge["id"]
    assert body["amount_cents"] == 2500
    assert body["tx_hash"] == "0xtxhash"
    assert body["status"] == "pending"
    assert body["id"]
    assert fake.calls == [("0xwallet-address", 25_000_000)]
    assert "0xwallet-address" not in caplog.text


def test_onchain_payout_reconciles_against_the_charge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeCoinbaseClient()
    _enable_onchain_settlement(monkeypatch, fake)
    charge = _create_charge(2500)
    client.post(
        "/settlements/onchain",
        json={
            "charge_id": charge["id"],
            "amount_cents": 2500,
            "destination_address": "0xwallet-address",
        },
        headers={"Idempotency-Key": "payout-1"},
    )

    assert len(reconcile.settlement_lines) == 1
    line = reconcile.settlement_lines[0]
    assert line.processor_ref == "0xtxhash"
    assert line.amount_cents == 2500
    assert line.charge_id == charge["id"]

    reconciliation = client.get("/merchants/merchant-123/reconciliation")
    assert reconciliation.json()["matched"] == [
        {
            "charge_id": charge["id"],
            "ledger_amount_cents": 2500,
            "settled_amount_cents": 2500,
        }
    ]


def test_refunded_amount_is_not_payoutable(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeCoinbaseClient()
    _enable_onchain_settlement(monkeypatch, fake)
    charge = _create_charge(10_000)
    reconcile.issue_refund(charge["id"], 4_000, "customer request")

    capped = client.post(
        "/settlements/onchain",
        json={
            "charge_id": charge["id"],
            "amount_cents": 6_000,
            "destination_address": "0xwallet-address",
        },
        headers={"Idempotency-Key": "payout-ok"},
    )
    over = client.post(
        "/settlements/onchain",
        json={
            "charge_id": charge["id"],
            "amount_cents": 6_001,
            "destination_address": "0xwallet-address",
        },
        headers={"Idempotency-Key": "payout-over"},
    )

    assert capped.status_code == 200
    assert over.status_code == 400
    assert over.json() == {
        "detail": "Settlement amount cannot exceed refundable amount"
    }
    assert len(reconcile.settlement_lines) == 1
    assert len(fake.calls) == 1


def test_non_positive_amount_returns_bad_request_without_recording(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeCoinbaseClient()
    _enable_onchain_settlement(monkeypatch, fake)
    charge = _create_charge(2500)

    for amount in (0, -100):
        response = client.post(
            "/settlements/onchain",
            json={
                "charge_id": charge["id"],
                "amount_cents": amount,
                "destination_address": "0xwallet-address",
            },
            headers={"Idempotency-Key": f"payout-{amount}"},
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "Settlement amount must be positive"}

    assert reconcile.settlement_lines == []
    assert fake.calls == []


def test_unknown_charge_returns_404_without_mutating_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeCoinbaseClient()
    _enable_onchain_settlement(monkeypatch, fake)

    response = client.post(
        "/settlements/onchain",
        json={
            "charge_id": "missing-charge",
            "amount_cents": 2500,
            "destination_address": "0xwallet-address",
        },
        headers={"Idempotency-Key": "payout-1"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Charge not found"}
    assert reconcile.settlement_lines == []
    assert fake.calls == []


def test_disabled_flag_returns_503_and_never_calls_coinbase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeCoinbaseClient()
    monkeypatch.setattr(main, "coinbase_client", fake)
    charge = _create_charge(2500)

    response = client.post(
        "/settlements/onchain",
        json={
            "charge_id": charge["id"],
            "amount_cents": 2500,
            "destination_address": "0xwallet-address",
        },
        headers={"Idempotency-Key": "payout-1"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Onchain settlement is disabled"}
    assert reconcile.settlement_lines == []
    assert fake.calls == []


def test_coinbase_rejection_returns_502_and_leaves_ledger_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeCoinbaseClient()
    fake.error = CoinbaseTransferError("insufficient funds")
    _enable_onchain_settlement(monkeypatch, fake)
    charge = _create_charge(2500)

    response = client.post(
        "/settlements/onchain",
        json={
            "charge_id": charge["id"],
            "amount_cents": 2500,
            "destination_address": "0xwallet-address",
        },
        headers={"Idempotency-Key": "payout-1"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Coinbase rejected the transfer"}
    assert reconcile.settlement_lines == []
    assert "0xwallet-address" not in response.text


def test_retry_with_same_idempotency_key_does_not_double_payout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeCoinbaseClient()
    _enable_onchain_settlement(monkeypatch, fake)
    charge = _create_charge(2500)
    payload = {
        "charge_id": charge["id"],
        "amount_cents": 2500,
        "destination_address": "0xwallet-address",
    }

    first = client.post(
        "/settlements/onchain", json=payload, headers={"Idempotency-Key": "payout-1"}
    )
    retry = client.post(
        "/settlements/onchain", json=payload, headers={"Idempotency-Key": "payout-1"}
    )

    assert first.status_code == 200
    assert retry.status_code == 200
    assert retry.json() == first.json()
    assert len(fake.calls) == 1
    assert len(reconcile.settlement_lines) == 1


def test_reused_payout_cap_across_distinct_idempotency_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeCoinbaseClient()
    _enable_onchain_settlement(monkeypatch, fake)
    charge = _create_charge(2500)
    payload = {
        "charge_id": charge["id"],
        "amount_cents": 2500,
        "destination_address": "0xwallet-address",
    }

    first = client.post(
        "/settlements/onchain", json=payload, headers={"Idempotency-Key": "payout-1"}
    )
    second = client.post(
        "/settlements/onchain", json=payload, headers={"Idempotency-Key": "payout-2"}
    )

    assert first.status_code == 200
    assert second.status_code == 400
    assert len(fake.calls) == 1
    assert len(reconcile.settlement_lines) == 1
