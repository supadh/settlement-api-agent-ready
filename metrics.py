from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests handled by the service",
    ("method", "route", "status"),
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "route"),
)
CHARGES_RECORDED = Counter(
    "charges_recorded_total", "Charges recorded in the in-memory ledger"
)
REFUNDS_ISSUED = Counter(
    "refunds_issued_total", "Refunds issued from the in-memory ledger"
)
SETTLEMENT_LINES_LOADED = Counter(
    "settlement_lines_loaded_total",
    "Settlement lines loaded into the in-memory ledger",
)
RECONCILIATION_MISMATCHES = Counter(
    "reconciliation_mismatches_total",
    "Charge mismatches found during merchant reconciliation",
)
