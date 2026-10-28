from datetime import datetime, timedelta, timezone

import pytest

import reconcile
from feature_flags import FeatureFlags
from reconcile import HIGH_REFUND_RATIO_PERCENT


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


def test_list_refunds_orders_newest_first() -> None:
    charge = reconcile.record_charge("merchant-123", 10_000, "card-token")
    reconcile.issue_refund(charge["id"], 1_000, "first request")
    reconcile.issue_refund(charge["id"], 2_000, "second request")
    reconcile.refunds[0].created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    reconcile.refunds[1].created_at = datetime(2026, 1, 2, tzinfo=timezone.utc)

    history = reconcile.list_refunds_for_charge(charge["id"])

    assert [refund["id"] for refund in history["refunds"]] == [
        reconcile.refunds[1].id,
        reconcile.refunds[0].id,
    ]


def test_list_refunds_sums_partial_refunds_exactly() -> None:
    charge = reconcile.record_charge("merchant-123", 10_000, "card-token")
    reconcile.issue_refund(charge["id"], 1_000, "first request")
    reconcile.issue_refund(charge["id"], 2_000, "second request")
    reconcile.issue_refund(charge["id"], 3_333, "third request")

    history = reconcile.list_refunds_for_charge(charge["id"])

    assert history["charge_id"] == charge["id"]
    assert history["charge_amount_cents"] == 10_000
    assert history["total_refunded_cents"] == 6_333
    assert history["refundable_balance_cents"] == 3_667
    assert len(history["refunds"]) == 3


def test_list_refunds_for_charge_without_refunds_returns_full_balance() -> None:
    charge = reconcile.record_charge("merchant-123", 7_500, "card-token")

    history = reconcile.list_refunds_for_charge(charge["id"])

    assert history["refunds"] == []
    assert history["total_refunded_cents"] == 0
    assert history["refundable_balance_cents"] == 7_500


def test_list_refunds_for_unknown_charge_is_rejected() -> None:
    with pytest.raises(ValueError, match="Charge not found"):
        reconcile.list_refunds_for_charge("missing-charge")
def test_refund_reports_remaining_charge_balance() -> None:
    charge = reconcile.record_charge("merchant-123", 10_000, "card-token")

    partial = reconcile.issue_refund(charge["id"], 4_000, "partial request")
    full = reconcile.issue_refund(charge["id"], 6_000, "final request")

    assert partial["remaining_charge_cents"] == 6_000
    assert full["remaining_charge_cents"] == 0


def test_rejected_over_refund_leaves_refunds_unchanged() -> None:
    charge = reconcile.record_charge("merchant-123", 10_000, "card-token")
    reconcile.issue_refund(charge["id"], 4_000, "partial request")
    refunds_before = list(reconcile.refunds)

    with pytest.raises(ValueError, match="cannot exceed"):
        reconcile.issue_refund(charge["id"], 6_001, "over-balance request")

    assert reconcile.refunds == refunds_before


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
        {
            "FEATURE_STRICT_SETTLEMENT_VALIDATION": "true",
            "FEATURE_ONCHAIN_SETTLEMENT": "true",
            "FEATURE_HIGH_REFUND_FLAGGING": "true",
        }
    )

    assert flags.strict_settlement_validation is True
    assert flags.onchain_settlement_enabled is True
    assert flags.high_refund_flagging is True


def test_high_refund_flagging_defaults_to_off() -> None:
    flags = FeatureFlags.from_environment({})

    assert flags.high_refund_flagging is False


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


def test_high_refund_charges_omitted_by_default() -> None:
    charge = reconcile.record_charge("merchant-123", 10_000, "card-token")
    reconcile.issue_refund(charge["id"], 9_001, "customer request")

    report = reconcile.reconcile_merchant("merchant-123")

    assert "high_refund_charges" not in report


def test_high_refund_charges_flagged_strictly_over_90_percent() -> None:
    charge = reconcile.record_charge("merchant-123", 10_000, "card-token")
    reconcile.issue_refund(charge["id"], 9_001, "customer request")

    report = reconcile.reconcile_merchant(
        "merchant-123", include_high_refund_charges=True
    )

    assert report["high_refund_charges"] == [
        {
            "charge_id": charge["id"],
            "charge_amount_cents": 10_000,
            "refunded_cents": 9_001,
            "refund_ratio_percent": 90,
        }
    ]


def test_charge_refunded_exactly_90_percent_is_not_flagged() -> None:
    assert HIGH_REFUND_RATIO_PERCENT == 90
    charge = reconcile.record_charge("merchant-123", 10_000, "card-token")
    reconcile.issue_refund(charge["id"], 9_000, "customer request")

    report = reconcile.reconcile_merchant(
        "merchant-123", include_high_refund_charges=True
    )

    assert report["high_refund_charges"] == []


def test_charge_refunded_50_percent_is_not_flagged() -> None:
    charge = reconcile.record_charge("merchant-123", 10_000, "card-token")
    reconcile.issue_refund(charge["id"], 5_000, "customer request")

    report = reconcile.reconcile_merchant(
        "merchant-123", include_high_refund_charges=True
    )

    assert report["high_refund_charges"] == []


def test_fully_refunded_charge_is_flagged_at_100_percent() -> None:
    charge = reconcile.record_charge("merchant-123", 4_000, "card-token")
    reconcile.issue_refund(charge["id"], 4_000, "customer request")

    report = reconcile.reconcile_merchant(
        "merchant-123", include_high_refund_charges=True
    )

    assert report["high_refund_charges"] == [
        {
            "charge_id": charge["id"],
            "charge_amount_cents": 4_000,
            "refunded_cents": 4_000,
            "refund_ratio_percent": 100,
        }
    ]


def test_multiple_high_refund_charges_are_listed_in_charge_order() -> None:
    first = reconcile.record_charge("merchant-123", 1_000, "card-token")
    second = reconcile.record_charge("merchant-123", 2_000, "card-token")
    reconcile.record_charge("merchant-123", 10_000, "card-token")
    reconcile.issue_refund(second["id"], 2_000, "customer request")
    reconcile.issue_refund(first["id"], 901, "customer request")

    report = reconcile.reconcile_merchant(
        "merchant-123", include_high_refund_charges=True
    )

    assert [entry["charge_id"] for entry in report["high_refund_charges"]] == [
        first["id"],
        second["id"],
    ]


def test_matched_and_mismatched_are_unchanged_when_high_refund_charges_included() -> (
    None
):
    charge = reconcile.record_charge("merchant-123", 10_000, "card-token")
    reconcile.issue_refund(charge["id"], 9_001, "customer request")
    reconcile.load_settlement_line("processor-ref", charge["id"], 990)

    flagged = reconcile.reconcile_merchant(
        "merchant-123", include_high_refund_charges=True
    )
    unflagged = reconcile.reconcile_merchant("merchant-123")

    assert flagged["matched"] == unflagged["matched"] == []
    assert (
        flagged["mismatched"]
        == unflagged["mismatched"]
        == [
            {
                "charge_id": charge["id"],
                "ledger_amount_cents": 999,
                "settled_amount_cents": 990,
                "difference_cents": -9,
            }
        ]
    )


def test_unknown_merchant_returns_empty_high_refund_charges() -> None:
    report = reconcile.reconcile_merchant(
        "merchant-unknown", include_high_refund_charges=True
    )

    assert report["high_refund_charges"] == []
