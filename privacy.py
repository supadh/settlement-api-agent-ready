from collections.abc import Mapping
from dataclasses import dataclass
from hmac import compare_digest
from os import environ
from typing import Optional

from secret_config import read_secret


@dataclass(frozen=True)
class PrivacySettings:
    data_retention_days: int
    admin_api_key: Optional[str]

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] = environ
    ) -> "PrivacySettings":
        raw_retention = environment.get("DATA_RETENTION_DAYS", "30")
        try:
            retention_days = int(raw_retention)
        except ValueError as error:
            raise ValueError(
                "DATA_RETENTION_DAYS must be a positive integer"
            ) from error
        if retention_days <= 0:
            raise ValueError("DATA_RETENTION_DAYS must be a positive integer")
        return cls(
            data_retention_days=retention_days,
            admin_api_key=read_secret(environment, "ADMIN_API_KEY"),
        )

    def authorizes(self, candidate: Optional[str]) -> bool:
        if self.admin_api_key is None or candidate is None:
            return False
        return compare_digest(self.admin_api_key, candidate)


privacy_settings = PrivacySettings.from_environment()
