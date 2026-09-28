from pathlib import Path

import pytest

from privacy import PrivacySettings
from secret_config import read_secret


def test_secret_can_be_loaded_from_a_mounted_file(tmp_path: Path) -> None:
    secret_file = tmp_path / "admin-api-key"
    secret_file.write_text("mounted-secret\n", encoding="utf-8")

    value = read_secret(
        {"ADMIN_API_KEY_FILE": str(secret_file)},
        "ADMIN_API_KEY",
    )

    assert value == "mounted-secret"


def test_secret_rejects_ambiguous_sources(tmp_path: Path) -> None:
    secret_file = tmp_path / "admin-api-key"
    secret_file.write_text("mounted-secret", encoding="utf-8")

    with pytest.raises(ValueError, match="Configure only one"):
        read_secret(
            {
                "ADMIN_API_KEY": "direct-secret",
                "ADMIN_API_KEY_FILE": str(secret_file),
            },
            "ADMIN_API_KEY",
        )


def test_privacy_settings_require_positive_retention() -> None:
    with pytest.raises(
        ValueError, match="DATA_RETENTION_DAYS must be a positive integer"
    ):
        PrivacySettings.from_environment({"DATA_RETENTION_DAYS": "0"})


def test_privacy_admin_key_uses_constant_time_comparison() -> None:
    settings = PrivacySettings(
        data_retention_days=30,
        admin_api_key="admin-secret",
    )

    assert settings.authorizes("admin-secret")
    assert not settings.authorizes("wrong-secret")
    assert not settings.authorizes(None)
