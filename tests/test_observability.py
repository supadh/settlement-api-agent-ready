import pytest

from observability import (
    Observability,
    ObservabilitySettings,
    anonymize_identifier,
    scrub_sentry_event,
)


def test_observability_is_disabled_without_credentials() -> None:
    settings = ObservabilitySettings.from_environment({})
    observability = Observability(settings)

    observability.initialize()
    observability.capture_product_event("test.event", "merchant-123")


def test_observability_rejects_invalid_sample_rates() -> None:
    with pytest.raises(ValueError, match="SENTRY_TRACES_SAMPLE_RATE must be a number"):
        ObservabilitySettings.from_environment({"SENTRY_TRACES_SAMPLE_RATE": "1.5"})


def test_identifier_anonymization_is_stable_and_non_reversible() -> None:
    first = anonymize_identifier("merchant-123")
    second = anonymize_identifier("merchant-123")

    assert first == second
    assert first != "merchant-123"
    assert len(first) == 16


def test_sentry_events_drop_requests_and_redact_secrets() -> None:
    scrubbed = scrub_sentry_event(
        {
            "request": {"url": "/merchants/merchant-123/reconciliation"},
            "extra": {"api_key": "secret-value"},
        },
        {},
    )

    assert scrubbed is not None
    assert "request" not in scrubbed
    assert scrubbed["extra"]["api_key"] == "[REDACTED]"
