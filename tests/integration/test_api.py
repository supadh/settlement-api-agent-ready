from unittest.mock import Mock

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import main
from feature_flags import FeatureFlags
from observability import observability as service_observability
from privacy import PrivacySettings

client = TestClient(main.app)


def test_health_and_request_security_headers() -> None:
    health_response = client.get("/health", headers={"X-Request-ID": "qa-request-id"})
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
    assert health_response.headers["X-Request-ID"] == "qa-request-id"
    assert health_response.headers["X-Content-Type-Options"] == "nosniff"
    assert health_response.headers["X-Frame-Options"] == "DENY"
    assert health_response.headers["Referrer-Policy"] == "no-referrer"
    assert health_response.headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert health_response.headers["Cache-Control"] == "no-store"


def test_readiness_reports_storage_status() -> None:
    readiness_response = client.get("/ready")
    assert readiness_response.status_code == 200
    assert readiness_response.json() == {
        "status": "ready",
        "storage": "in-memory",
    }


def test_metrics_endpoint_exposes_service_metrics() -> None:
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert "http_requests_total" in metrics_response.text
    assert "reconciliation_mismatches_total" in metrics_response.text


def test_charge_settlement_and_reconciliation_flow() -> None:
    charge_response = client.post(
        "/charges",
        json={
            "merchant_id": "merchant-123",
            "amount_cents": 2500,
            "card_token": "card-token",
        },
    )
    assert charge_response.status_code == 200
    assert "card_token" not in charge_response.json()
    assert "merchant_id" not in charge_response.json()
    charge_id = charge_response.json()["id"]

    settlement_response = client.post(
        "/settlement-lines",
        json={
            "processor_ref": "processor-ref-1",
            "charge_id": charge_id,
            "amount_cents": 2500,
        },
    )
    assert settlement_response.status_code == 200

    reconciliation_response = client.get("/merchants/merchant-123/reconciliation")
    assert reconciliation_response.status_code == 200
    assert reconciliation_response.json() == {
        "merchant_id": "merchant-123",
        "matched": [
            {
                "charge_id": charge_id,
                "ledger_amount_cents": 2500,
                "settled_amount_cents": 2500,
            }
        ],
        "mismatched": [],
    }


def test_refund_for_unknown_charge_returns_bad_request() -> None:
    response = client.post(
        "/charges/missing-charge/refunds",
        json={"amount_cents": 100, "reason": "customer request"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Charge not found"}


def test_reconciliation_lists_high_refund_charges_when_enabled(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "feature_flags", FeatureFlags(high_refund_flagging=True))
    charge_response = client.post(
        "/charges",
        json={
            "merchant_id": "merchant-123",
            "amount_cents": 10_000,
            "card_token": "card-token",
        },
    )
    charge_id = charge_response.json()["id"]
    refund_response = client.post(
        f"/charges/{charge_id}/refunds",
        json={"amount_cents": 9_001, "reason": "customer request"},
    )
    assert refund_response.status_code == 200

    response = client.get("/merchants/merchant-123/reconciliation")

    assert response.status_code == 200
    assert response.json() == {
        "merchant_id": "merchant-123",
        "matched": [],
        "mismatched": [
            {
                "charge_id": charge_id,
                "ledger_amount_cents": 999,
                "settled_amount_cents": 0,
                "difference_cents": -999,
            }
        ],
        "high_refund_charges": [
            {
                "charge_id": charge_id,
                "charge_amount_cents": 10_000,
                "refunded_cents": 9_001,
                "refund_ratio_percent": 90,
            }
        ],
    }


def test_validation_errors_do_not_reflect_card_tokens() -> None:
    response = client.post(
        "/charges",
        json={
            "merchant_id": "merchant-123",
            "amount_cents": 2500,
            "card_token": None,
        },
    )

    assert response.status_code == 422
    assert "input" not in response.json()["detail"][0]


def test_container_validation_errors_do_not_reflect_tokens() -> None:
    response = client.post(
        "/charges",
        json=[
            {
                "merchant_id": "merchant-123",
                "amount_cents": 2500,
                "card_token": "must-not-be-reflected",
            }
        ],
    )

    assert response.status_code == 422
    assert "must-not-be-reflected" not in response.text


def test_whitespace_card_token_returns_client_error() -> None:
    response = client.post(
        "/charges",
        json={
            "merchant_id": "merchant-123",
            "amount_cents": 2500,
            "card_token": "   ",
        },
    )

    assert response.status_code == 400


def test_privacy_export_requires_admin_key_and_excludes_tokens(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "privacy_settings",
        PrivacySettings(data_retention_days=30, admin_api_key="admin-secret"),
    )
    client.post(
        "/charges",
        json={
            "merchant_id": "merchant-123",
            "amount_cents": 2500,
            "card_token": "processor-token",
        },
    )

    denied = client.get("/admin/privacy/merchants/merchant-123")
    exported = client.get(
        "/admin/privacy/merchants/merchant-123",
        headers={"X-Admin-Key": "admin-secret"},
    )

    assert denied.status_code == 403
    assert exported.status_code == 200
    assert "processor-token" not in exported.text
    assert len(exported.json()["charges"]) == 1


def test_privacy_deletion_removes_merchant_records(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "privacy_settings",
        PrivacySettings(data_retention_days=30, admin_api_key="admin-secret"),
    )
    client.post(
        "/charges",
        json={
            "merchant_id": "merchant-123",
            "amount_cents": 2500,
            "card_token": "processor-token",
        },
    )

    deleted = client.delete(
        "/admin/privacy/merchants/merchant-123",
        headers={"X-Admin-Key": "admin-secret"},
    )
    exported = client.get(
        "/admin/privacy/merchants/merchant-123",
        headers={"X-Admin-Key": "admin-secret"},
    )

    assert deleted.status_code == 200
    assert deleted.json()["deleted"]["charges"] == 1
    assert exported.json()["charges"] == []


def test_refund_analytics_use_merchant_identity(
    monkeypatch: MonkeyPatch,
) -> None:
    capture_event = Mock()
    monkeypatch.setattr(
        service_observability,
        "capture_product_event",
        capture_event,
    )
    charge = client.post(
        "/charges",
        json={
            "merchant_id": "merchant-123",
            "amount_cents": 2500,
            "card_token": "processor-token",
        },
    ).json()
    capture_event.reset_mock()

    response = client.post(
        f"/charges/{charge['id']}/refunds",
        json={"amount_cents": 500, "reason": "customer request"},
    )

    assert response.status_code == 200
    capture_event.assert_called_once_with(
        "settlement.refund_created",
        "merchant-123",
    )
