from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from typing_extensions import NotRequired, TypedDict

from logging_config import logger
from metrics import (
    CHARGES_RECORDED,
    RECONCILIATION_MISMATCHES,
    REFUNDS_ISSUED,
    SETTLEMENT_LINES_LOADED,
)

HIGH_REFUND_RATIO_PERCENT = 90


@dataclass
class Charge:
    id: str
    merchant_id: str
    amount_cents: int
    created_at: datetime


@dataclass
class Refund:
    id: str
    charge_id: str
    amount_cents: int
    reason: str
    created_at: datetime


@dataclass
class SettlementLine:
    processor_ref: str
    charge_id: str
    amount_cents: int
    created_at: datetime


class ChargeData(TypedDict):
    id: str
    merchant_id: str
    amount_cents: int
    created_at: datetime


class RefundData(TypedDict):
    id: str
    charge_id: str
    amount_cents: int
    reason: str
    created_at: datetime


class SettlementLineData(TypedDict):
    processor_ref: str
    charge_id: str
    amount_cents: int
    created_at: datetime


class MatchResult(TypedDict):
    charge_id: str
    ledger_amount_cents: int
    settled_amount_cents: int


class MismatchResult(MatchResult):
    difference_cents: int


class HighRefundFlagData(TypedDict):
    charge_id: str
    charge_amount_cents: int
    refunded_cents: int
    refund_ratio_percent: int


class ReconciliationData(TypedDict):
    merchant_id: str
    matched: list[MatchResult]
    mismatched: list[MismatchResult]
    high_refund_charges: NotRequired[list[HighRefundFlagData]]


class MerchantExportData(TypedDict):
    merchant_id: str
    charges: list[ChargeData]
    refunds: list[RefundData]
    settlement_lines: list[SettlementLineData]


charges: dict[str, Charge] = {}
refunds: list[Refund] = []
settlement_lines: list[SettlementLine] = []


def _charge_data(charge: Charge) -> ChargeData:
    return {
        "id": charge.id,
        "merchant_id": charge.merchant_id,
        "amount_cents": charge.amount_cents,
        "created_at": charge.created_at,
    }


def _refund_data(refund: Refund) -> RefundData:
    return {
        "id": refund.id,
        "charge_id": refund.charge_id,
        "amount_cents": refund.amount_cents,
        "reason": refund.reason,
        "created_at": refund.created_at,
    }


def _settlement_line_data(line: SettlementLine) -> SettlementLineData:
    return {
        "processor_ref": line.processor_ref,
        "charge_id": line.charge_id,
        "amount_cents": line.amount_cents,
        "created_at": line.created_at,
    }


def record_charge(merchant_id: str, amount_cents: int, card_token: str) -> ChargeData:
    if not card_token.strip():
        raise ValueError("Card token must not be empty")
    charge = Charge(
        id=str(uuid4()),
        merchant_id=merchant_id,
        amount_cents=amount_cents,
        created_at=datetime.now(timezone.utc),
    )
    charges[charge.id] = charge
    CHARGES_RECORDED.inc()
    logger.info("charge.recorded", extra={"charge_id": charge.id})
    return _charge_data(charge)


def issue_refund(charge_id: str, amount_cents: int, reason: str) -> RefundData:
    charge = charges.get(charge_id)
    if charge is None:
        raise ValueError("Charge not found")
    if amount_cents <= 0:
        raise ValueError("Refund amount must be positive")
    refunded_cents = sum(
        refund.amount_cents for refund in refunds if refund.charge_id == charge_id
    )
    if refunded_cents + amount_cents > charge.amount_cents:
        raise ValueError("Refund amount cannot exceed charge amount")

    refund = Refund(
        id=str(uuid4()),
        charge_id=charge_id,
        amount_cents=amount_cents,
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )
    refunds.append(refund)
    REFUNDS_ISSUED.inc()
    logger.info(
        "refund.issued",
        extra={"refund_id": refund.id, "charge_id": charge_id},
    )
    return _refund_data(refund)


def merchant_id_for_charge(charge_id: str) -> str:
    charge = charges.get(charge_id)
    if charge is None:
        raise ValueError("Charge not found")
    return charge.merchant_id


def load_settlement_line(
    processor_ref: str,
    charge_id: str,
    amount_cents: int,
    *,
    strict_validation: bool = False,
) -> SettlementLineData:
    if strict_validation:
        if charge_id not in charges:
            raise ValueError("Charge not found")
        if amount_cents <= 0:
            raise ValueError("Settlement amount must be positive")

    line = SettlementLine(
        processor_ref=processor_ref,
        charge_id=charge_id,
        amount_cents=amount_cents,
        created_at=datetime.now(timezone.utc),
    )
    settlement_lines.append(line)
    SETTLEMENT_LINES_LOADED.inc()
    logger.info(
        "settlement_line.loaded",
        extra={"charge_id": charge_id},
    )
    return _settlement_line_data(line)


def _refunded_cents(charge_id: str) -> int:
    return sum(
        refund.amount_cents for refund in refunds if refund.charge_id == charge_id
    )


def _settled_cents(charge_id: str) -> int:
    return sum(
        line.amount_cents for line in settlement_lines if line.charge_id == charge_id
    )


def _high_refund_flag(charge: Charge, refunded_cents: int) -> HighRefundFlagData | None:
    if refunded_cents * 100 <= charge.amount_cents * HIGH_REFUND_RATIO_PERCENT:
        return None
    return {
        "charge_id": charge.id,
        "charge_amount_cents": charge.amount_cents,
        "refunded_cents": refunded_cents,
        "refund_ratio_percent": refunded_cents * 100 // charge.amount_cents,
    }


def reconcile_merchant(
    merchant_id: str, include_high_refund_charges: bool = False
) -> ReconciliationData:
    matched: list[MatchResult] = []
    mismatched: list[MismatchResult] = []
    high_refund_charges: list[HighRefundFlagData] = []

    merchant_charges = [
        charge for charge in charges.values() if charge.merchant_id == merchant_id
    ]
    for charge in merchant_charges:
        refunded_cents = _refunded_cents(charge.id)
        settled_cents = _settled_cents(charge.id)
        ledger_cents = charge.amount_cents - refunded_cents
        if ledger_cents == settled_cents:
            matched.append(
                {
                    "charge_id": charge.id,
                    "ledger_amount_cents": ledger_cents,
                    "settled_amount_cents": settled_cents,
                }
            )
        else:
            mismatched.append(
                {
                    "charge_id": charge.id,
                    "ledger_amount_cents": ledger_cents,
                    "settled_amount_cents": settled_cents,
                    "difference_cents": settled_cents - ledger_cents,
                }
            )
        flag = _high_refund_flag(charge, refunded_cents)
        if flag is not None:
            high_refund_charges.append(flag)

    RECONCILIATION_MISMATCHES.inc(len(mismatched))
    logger.info(
        "merchant.reconciled",
        extra={
            "matched_count": len(matched),
            "mismatched_count": len(mismatched),
        },
    )
    result: ReconciliationData = {
        "merchant_id": merchant_id,
        "matched": matched,
        "mismatched": mismatched,
    }
    if include_high_refund_charges:
        result["high_refund_charges"] = high_refund_charges
    return result


def export_merchant_data(merchant_id: str) -> MerchantExportData:
    merchant_charges = [
        charge for charge in charges.values() if charge.merchant_id == merchant_id
    ]
    charge_ids = {charge.id for charge in merchant_charges}
    return {
        "merchant_id": merchant_id,
        "charges": [_charge_data(charge) for charge in merchant_charges],
        "refunds": [
            _refund_data(refund) for refund in refunds if refund.charge_id in charge_ids
        ],
        "settlement_lines": [
            _settlement_line_data(line)
            for line in settlement_lines
            if line.charge_id in charge_ids
        ],
    }


def _delete_charge_ids(charge_ids: Iterable[str]) -> dict[str, int]:
    ids = set(charge_ids)
    deleted_charges = sum(charge_id in charges for charge_id in ids)
    for charge_id in ids:
        charges.pop(charge_id, None)

    original_refund_count = len(refunds)
    refunds[:] = [refund for refund in refunds if refund.charge_id not in ids]
    original_line_count = len(settlement_lines)
    settlement_lines[:] = [
        line for line in settlement_lines if line.charge_id not in ids
    ]
    return {
        "charges": deleted_charges,
        "refunds": original_refund_count - len(refunds),
        "settlement_lines": original_line_count - len(settlement_lines),
    }


def delete_merchant_data(merchant_id: str) -> dict[str, int]:
    charge_ids = [
        charge.id for charge in charges.values() if charge.merchant_id == merchant_id
    ]
    return _delete_charge_ids(charge_ids)


def purge_expired_data(cutoff: datetime) -> dict[str, int]:
    expired_charge_ids = [
        charge.id for charge in charges.values() if charge.created_at < cutoff
    ]
    deleted = _delete_charge_ids(expired_charge_ids)

    original_refund_count = len(refunds)
    refunds[:] = [refund for refund in refunds if refund.created_at >= cutoff]
    deleted["refunds"] += original_refund_count - len(refunds)

    original_line_count = len(settlement_lines)
    settlement_lines[:] = [
        line for line in settlement_lines if line.created_at >= cutoff
    ]
    deleted["settlement_lines"] += original_line_count - len(settlement_lines)
    return deleted
