from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from os import environ
from typing import Any, Optional, cast

import sentry_sdk
from posthog import Posthog
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.types import Event

from logging_config import redact_sensitive_data
from secret_config import read_secret


def _sample_rate(environment: Mapping[str, str], name: str) -> float:
    raw_value = environment.get(name, "0.0")
    try:
        value = float(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be a number between 0 and 1") from error
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be a number between 0 and 1")
    return value


def scrub_sentry_event(event: Event, _hint: dict[str, Any]) -> Optional[Event]:
    scrubbed_event = cast(Event, redact_sensitive_data(event))
    scrubbed_event.pop("request", None)
    return scrubbed_event


@dataclass(frozen=True)
class ObservabilitySettings:
    environment: str
    release: str
    sentry_dsn: Optional[str]
    sentry_traces_sample_rate: float
    sentry_profiles_sample_rate: float
    posthog_api_key: Optional[str]
    posthog_host: str

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] = environ
    ) -> "ObservabilitySettings":
        return cls(
            environment=environment.get("APP_ENVIRONMENT", "development"),
            release=environment.get("APP_RELEASE", "local"),
            sentry_dsn=read_secret(environment, "SENTRY_DSN"),
            sentry_traces_sample_rate=_sample_rate(
                environment, "SENTRY_TRACES_SAMPLE_RATE"
            ),
            sentry_profiles_sample_rate=_sample_rate(
                environment, "SENTRY_PROFILES_SAMPLE_RATE"
            ),
            posthog_api_key=read_secret(environment, "POSTHOG_API_KEY"),
            posthog_host=environment.get("POSTHOG_HOST", "https://us.i.posthog.com"),
        )


class Observability:
    def __init__(self, settings: ObservabilitySettings) -> None:
        self.settings = settings
        self._posthog: Optional[Posthog] = None

    def initialize(self) -> None:
        if self.settings.sentry_dsn:
            sentry_sdk.init(
                dsn=self.settings.sentry_dsn,
                environment=self.settings.environment,
                release=self.settings.release,
                send_default_pii=False,
                max_request_body_size="never",
                before_send=scrub_sentry_event,
                traces_sample_rate=self.settings.sentry_traces_sample_rate,
                profiles_sample_rate=self.settings.sentry_profiles_sample_rate,
                integrations=[FastApiIntegration()],
            )

        if self.settings.posthog_api_key:
            self._posthog = Posthog(
                self.settings.posthog_api_key,
                host=self.settings.posthog_host,
            )

    def capture_product_event(
        self,
        event: str,
        merchant_id: str,
        properties: Optional[dict[str, object]] = None,
    ) -> None:
        if self._posthog is None:
            return
        self._posthog.capture(
            distinct_id=anonymize_identifier(merchant_id),
            event=event,
            properties={
                "environment": self.settings.environment,
                "release": self.settings.release,
                **(properties or {}),
            },
        )


def anonymize_identifier(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:16]


observability = Observability(ObservabilitySettings.from_environment())
observability.initialize()
