import json
import logging
from io import StringIO

from logging_config import RedactingJsonFormatter, request_id_context


def test_json_logging_adds_request_id_and_redacts_sensitive_fields() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingJsonFormatter())
    test_logger = logging.getLogger("test.redaction")
    test_logger.handlers = [handler]
    test_logger.propagate = False
    test_logger.setLevel(logging.INFO)
    token = request_id_context.set("request-123")

    try:
        test_logger.info(
            "safe event",
            extra={
                "payload": {
                    "merchant_id": "merchant-123",
                    "card_token": "sensitive-token",
                    "contact": {
                        "email": "merchant@example.com",
                        "stripe_api_key": "secret-key",
                    },
                }
            },
        )
    finally:
        request_id_context.reset(token)

    record = json.loads(stream.getvalue())
    assert record["request_id"] == "request-123"
    assert record["payload"]["merchant_id"] == "[REDACTED]"
    assert record["payload"]["card_token"] == "[REDACTED]"
    assert record["payload"]["contact"]["email"] == "[REDACTED]"
    assert record["payload"]["contact"]["stripe_api_key"] == "[REDACTED]"
