import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from os import environ
from typing import Any, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field
from sentry_sdk import set_tag

from feature_flags import feature_flags
from logging_config import (
    configure_logging,
    logger,
    request_id_context,
)
from metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS
from observability import observability
from privacy import privacy_settings
from reconcile import (
    ChargeData,
    MerchantExportData,
    ReconciliationData,
    RefundData,
    RefundHistoryData,
    SettlementLineData,
    delete_merchant_data,
    export_merchant_data,
    issue_refund,
    list_refunds_for_charge,
    load_settlement_line,
    merchant_id_for_charge,
    purge_expired_data,
    reconcile_merchant,
    record_charge,
)

configure_logging(environ.get("LOG_LEVEL", "INFO"))
app = FastAPI(title="Meridian Pay Settlement API")
admin_api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


class ChargeRequest(BaseModel):
    merchant_id: str = Field(min_length=1, max_length=128)
    amount_cents: int = Field(gt=0, le=999_999_999_999)
    card_token: str = Field(min_length=1, max_length=512)


class RefundRequest(BaseModel):
    amount_cents: int = Field(gt=0, le=999_999_999_999)
    reason: str = Field(min_length=1, max_length=500)


class SettlementLineRequest(BaseModel):
    processor_ref: str = Field(min_length=1, max_length=255)
    charge_id: str = Field(min_length=1, max_length=64)
    amount_cents: int = Field(gt=0, le=999_999_999_999)


class ChargeResponse(BaseModel):
    id: str
    amount_cents: int


class RefundResponse(BaseModel):
    id: str
    charge_id: str
    amount_cents: int
    remaining_charge_cents: int


class RefundHistoryItemResponse(BaseModel):
    id: str
    charge_id: str
    amount_cents: int
    reason: str
    created_at: datetime


class RefundHistoryResponse(BaseModel):
    charge_id: str
    charge_amount_cents: int
    total_refunded_cents: int
    refundable_balance_cents: int
    refunds: list[RefundHistoryItemResponse]


def require_admin_access(
    candidate: Optional[str] = Depends(admin_api_key_header),
) -> None:
    if privacy_settings.admin_api_key is None:
        raise HTTPException(status_code=503, detail="Admin API is disabled")
    if not privacy_settings.authorizes(candidate):
        raise HTTPException(status_code=403, detail="Forbidden")


def _safe_validation_errors(
    error: RequestValidationError,
) -> list[dict[str, Any]]:
    sanitized_errors: list[dict[str, Any]] = []
    for item in error.errors():
        sanitized = dict(item)
        sanitized.pop("input", None)
        sanitized_errors.append(sanitized)
    return sanitized_errors


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, error: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": _safe_validation_errors(error)},
    )


@app.middleware("http")
async def observe_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=privacy_settings.data_retention_days
    )
    purge_expired_data(cutoff)
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    context_token = request_id_context.set(request_id)
    set_tag("request_id", request_id)
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        route = _route_name(request)
        HTTP_REQUESTS.labels(request.method, route, "500").inc()
        logger.exception(
            "http.request_failed",
            extra={"http_method": request.method, "http_route": route},
        )
        raise
    else:
        route = _route_name(request)
        status = str(response.status_code)
        HTTP_REQUESTS.labels(request.method, route, status).inc()
        HTTP_REQUEST_DURATION.labels(request.method, route).observe(
            time.perf_counter() - started_at
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        logger.info(
            "http.request_completed",
            extra={
                "http_method": request.method,
                "http_route": route,
                "status_code": response.status_code,
            },
        )
        return response
    finally:
        request_id_context.reset(context_token)


def _route_name(request: Request) -> str:
    route = request.scope.get("route")
    return str(getattr(route, "path", "unmatched"))


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
def ready() -> dict[str, str]:
    return {"status": "ready", "storage": "in-memory"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/charges", response_model=ChargeResponse)
def create_charge(request: ChargeRequest) -> ChargeData:
    try:
        charge = record_charge(
            request.merchant_id,
            request.amount_cents,
            request.card_token,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    observability.capture_product_event(
        "settlement.charge_created",
        request.merchant_id,
    )
    return charge


@app.post("/charges/{charge_id}/refunds", response_model=RefundResponse)
def create_refund(charge_id: str, request: RefundRequest) -> RefundData:
    try:
        refund = issue_refund(charge_id, request.amount_cents, request.reason)
        observability.capture_product_event(
            "settlement.refund_created",
            merchant_id_for_charge(refund["charge_id"]),
        )
        return refund
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get(
    "/charges/{charge_id}/refunds",
    response_model=RefundHistoryResponse,
)
def get_refund_history(charge_id: str) -> RefundHistoryData:
    try:
        return list_refunds_for_charge(charge_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/settlement-lines")
def create_settlement_line(
    request: SettlementLineRequest,
) -> SettlementLineData:
    try:
        return load_settlement_line(
            request.processor_ref,
            request.charge_id,
            request.amount_cents,
            strict_validation=feature_flags.strict_settlement_validation,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/merchants/{merchant_id}/reconciliation")
def get_reconciliation(merchant_id: str) -> ReconciliationData:
    result = reconcile_merchant(
        merchant_id,
        include_high_refund_charges=feature_flags.high_refund_flagging,
    )
    observability.capture_product_event(
        "settlement.reconciliation_requested",
        merchant_id,
        {
            "matched_count": len(result["matched"]),
            "mismatched_count": len(result["mismatched"]),
        },
    )
    return result


@app.get(
    "/admin/privacy/merchants/{merchant_id}",
    include_in_schema=False,
    dependencies=[Depends(require_admin_access)],
)
def export_merchant_privacy_data(merchant_id: str) -> MerchantExportData:
    return export_merchant_data(merchant_id)


@app.delete(
    "/admin/privacy/merchants/{merchant_id}",
    include_in_schema=False,
    dependencies=[Depends(require_admin_access)],
)
def delete_merchant_privacy_data(
    merchant_id: str,
) -> dict[str, object]:
    return {
        "merchant_id": merchant_id,
        "deleted": delete_merchant_data(merchant_id),
    }
