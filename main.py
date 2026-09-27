from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from reconcile import (
    issue_refund,
    load_settlement_line,
    reconcile_merchant,
    record_charge,
)


app = FastAPI(title="Meridian Pay Settlement API")


class ChargeRequest(BaseModel):
    merchant_id: str
    amount_cents: int
    card_token: str


class RefundRequest(BaseModel):
    amount_cents: int
    reason: str


class SettlementLineRequest(BaseModel):
    processor_ref: str
    charge_id: str
    amount_cents: int


@app.post("/charges")
def create_charge(request: ChargeRequest):
    return record_charge(
        request.merchant_id,
        request.amount_cents,
        request.card_token,
    )


@app.post("/charges/{charge_id}/refunds")
def create_refund(charge_id: str, request: RefundRequest):
    try:
        return issue_refund(charge_id, request.amount_cents, request.reason)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/settlement-lines")
def create_settlement_line(request: SettlementLineRequest):
    return load_settlement_line(
        request.processor_ref,
        request.charge_id,
        request.amount_cents,
    )


@app.get("/merchants/{merchant_id}/reconciliation")
def get_reconciliation(merchant_id: str):
    return reconcile_merchant(merchant_id)
