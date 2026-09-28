from collections.abc import Mapping
from dataclasses import dataclass
from os import environ

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _read_bool(environment: Mapping[str, str], name: str, default: bool) -> bool:
    raw_value = environment.get(name)
    if raw_value is None:
        return default

    value = raw_value.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ValueError(
        f"{name} must be one of: {', '.join(sorted(TRUE_VALUES | FALSE_VALUES))}"
    )


@dataclass(frozen=True)
class FeatureFlags:
    strict_settlement_validation: bool = False

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] = environ
    ) -> "FeatureFlags":
        return cls(
            strict_settlement_validation=_read_bool(
                environment,
                "FEATURE_STRICT_SETTLEMENT_VALIDATION",
                default=False,
            )
        )


feature_flags = FeatureFlags.from_environment()
