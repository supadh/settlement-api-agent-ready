from dataclasses import asdict, dataclass
from uuid import uuid4


@dataclass
class Charge:
    id: str
    merchant_id: str
    amount_cents: int
    card_token: str


@dataclass
class Refund:
    id: str
    charge_id: str
    amount_cents: int
    reason: str


@dataclass
class SettlementLine:
    processor_ref: str
    charge_id: str
    amount_cents: int


charges: dict[str, Charge] = {}
refunds: list[Refund] = []
settlement_lines: list[SettlementLine] = []


def record_charge(merchant_id: str, amount_cents: int, card_token: str) -> dict:
    charge = Charge(
        id=str(uuid4()),
        merchant_id=merchant_id,
        amount_cents=amount_cents,
        card_token=card_token,
    )
    charges[charge.id] = charge
    print(f"Recorded charge {charge.id} for merchant {merchant_id}")
    return asdict(charge)


def issue_refund(charge_id: str, amount_cents: int, reason: str) -> dict:
    charge = charges.get(charge_id)
    if charge is None:
        raise ValueError("Charge not found")
    if amount_cents <= 0:
        raise ValueError("Refund amount must be positive")
    if amount_cents > charge.amount_cents:
        raise ValueError("Refund amount cannot exceed charge amount")

    refund = Refund(
        id=str(uuid4()),
        charge_id=charge_id,
        amount_cents=amount_cents,
        reason=reason,
    )
    refunds.append(refund)
    print(f"Issued refund {refund.id} against charge {charge_id}")
    return asdict(refund)


def load_settlement_line(
    processor_ref: str, charge_id: str, amount_cents: int
) -> dict:
    line = SettlementLine(
        processor_ref=processor_ref,
        charge_id=charge_id,
        amount_cents=amount_cents,
    )
    settlement_lines.append(line)
    print(f"Loaded settlement line {processor_ref} for charge {charge_id}")
    return asdict(line)


def reconcile_merchant(merchant_id: str) -> dict:
    matched = []
    mismatched = []

    merchant_charges = [
        charge for charge in charges.values() if charge.merchant_id == merchant_id
    ]
    for charge in merchant_charges:
        refunded_cents = sum(
            refund.amount_cents
            for refund in refunds
            if refund.charge_id == charge.id
        )
        settled_cents = sum(
            line.amount_cents
            for line in settlement_lines
            if line.charge_id == charge.id
        )
        ledger_cents = charge.amount_cents - refunded_cents
        result = {
            "charge_id": charge.id,
            "ledger_amount_cents": ledger_cents,
            "settled_amount_cents": settled_cents,
        }
        if ledger_cents == settled_cents:
            matched.append(result)
        else:
            result["difference_cents"] = settled_cents - ledger_cents
            mismatched.append(result)

    print(
        f"Reconciled merchant {merchant_id}: "
        f"{len(matched)} matched, {len(mismatched)} mismatched"
    )
    return {
        "merchant_id": merchant_id,
        "matched": matched,
        "mismatched": mismatched,
    }
