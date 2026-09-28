from collections.abc import Mapping
from pathlib import Path
from typing import Optional


def read_secret(
    environment: Mapping[str, str],
    name: str,
) -> Optional[str]:
    direct_value = environment.get(name, "").strip()
    file_name = environment.get(f"{name}_FILE", "").strip()
    if direct_value and file_name:
        raise ValueError(f"Configure only one of {name} or {name}_FILE")
    if file_name:
        value = Path(file_name).read_text(encoding="utf-8").strip()
    else:
        value = direct_value
    return value or None
