import logging
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any, cast

from pythonjsonlogger.json import JsonFormatter

request_id_context: ContextVar[str] = ContextVar("request_id", default="not-in-request")
SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "address",
        "api_key",
        "authorization",
        "card_token",
        "cookie",
        "cvv",
        "email",
        "first_name",
        "full_name",
        "last_name",
        "merchant_id",
        "password",
        "phone",
        "refresh_token",
        "secret",
        "ssn",
        "token",
    }
)
SENSITIVE_SUFFIXES = ("_key", "_password", "_secret", "_token")


def _is_sensitive_key(key: str) -> bool:
    normalized_key = key.lower()
    return normalized_key in SENSITIVE_KEYS or normalized_key.endswith(
        SENSITIVE_SUFFIXES
    )


def redact_sensitive_data(value: Any) -> Any:
    if isinstance(value, MutableMapping):
        return {
            key: (
                "[REDACTED]"
                if _is_sensitive_key(str(key))
                else redact_sensitive_data(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    return value


class RedactingJsonFormatter(JsonFormatter):
    def process_log_record(
        self, log_record: MutableMapping[str, Any]
    ) -> dict[str, Any]:
        log_record["request_id"] = request_id_context.get()
        return cast(dict[str, Any], redact_sensitive_data(log_record))


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        RedactingJsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())


logger = logging.getLogger("meridian.settlement")
