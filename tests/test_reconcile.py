from datetime import datetime, timedelta, timezone

import pytest

import reconcile
from feature_flags import FeatureFlags


def test_record_charge() -> None:
    charge = reconcile.record_charge("merchant-123", 2500, "card-token")

    assert charge["merchant_id"] == "merchant-123"
    assert charge["amount_cents"] == 2500
    assert "card_token" not in charge
    assert not hasattr(reconcile.charges[charge["id"]], "card_token")


def test_refund_larger_than_charge_is_rejected() -> None:
    charge = reconcile.record_charge("merchant-123", 2500, "card-token")

    with pytest.raises(ValueError):
        reconcile.issue_refund(charge["id"], 2501, "customer request")


def test_cumulative_refunds_cannot_exceed_charge() -> None:
    charge = reconcile.record_charge("merchant-123", 10_000, "card-token")
    reconcile.issue_refund(charge["id"], 6_000, "first request")

    with pytest.raises(ValueError, match="cannot exceed"):
        reconcile.issue_refund(charge["id"], 6_000, "second request")


def test_strict_settlement_validation_rejects_an_unknown_charge() -> None:
    with pytest.raises(ValueError, match="Charge not found"):
        reconcile.load_settlement_line(
            "processor-ref",
            "missing-charge",
            2500,
            strict_validation=True,
        )


def test_disabled_settlement_validation_preserves_legacy_ingestion() -> None:
    line = reconcile.load_settlement_line(
        "processor-ref",
        "missing-charge",
        2500,
        strict_validation=False,
    )

    assert line["charge_id"] == "missing-charge"


def test_feature_flags_are_loaded_from_the_environment() -> None:
    flags = FeatureFlags.from_environment(
        {"FEATURE_STRICT_SETTLEMENT_VALIDATION": "true"}
    )

    assert flags.strict_settlement_validation is True


def test_feature_flags_reject_invalid_boolean_values() -> None:
    with pytest.raises(
        ValueError,
        match="FEATURE_STRICT_SETTLEMENT_VALIDATION must be one of",
    ):
        FeatureFlags.from_environment(
            {"FEATURE_STRICT_SETTLEMENT_VALIDATION": "sometimes"}
        )


def test_merchant_export_and_deletion_cascade() -> None:
    charge = reconcile.record_charge("merchant-123", 2500, "card-token")
    reconcile.issue_refund(charge["id"], 500, "customer request")
    reconcile.load_settlement_line("processor-ref", charge["id"], 2000)

    exported = reconcile.export_merchant_data("merchant-123")
    deleted = reconcile.delete_merchant_data("merchant-123")

    assert "card_token" not in str(exported)
    assert len(exported["charges"]) == 1
    assert deleted == {"charges": 1, "refunds": 1, "settlement_lines": 1}
    assert reconcile.export_merchant_data("merchant-123")["charges"] == []


def test_expired_merchant_data_is_purged() -> None:
    charge = reconcile.record_charge("merchant-123", 2500, "card-token")
    reconcile.charges[charge["id"]].created_at = datetime.now(timezone.utc) - timedelta(
        days=31
    )

    deleted = reconcile.purge_expired_data(
        datetime.now(timezone.utc) - timedelta(days=30)
    )

    assert deleted["charges"] == 1
    assert charge["id"] not in reconcile.charges
