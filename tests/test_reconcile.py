import pytest

import reconcile


def test_record_charge():
    reconcile.charges.clear()

    charge = reconcile.record_charge("merchant-123", 2500, "card-token")

    assert charge["merchant_id"] == "merchant-123"
    assert charge["amount_cents"] == 2500
    assert charge["card_token"] == "card-token"


def test_refund_larger_than_charge_is_rejected():
    reconcile.charges.clear()
    reconcile.refunds.clear()
    charge = reconcile.record_charge("merchant-123", 2500, "card-token")

    with pytest.raises(ValueError):
        reconcile.issue_refund(charge["id"], 2501, "customer request")
