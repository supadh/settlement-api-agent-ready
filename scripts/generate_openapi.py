import json
import sys
from importlib import import_module
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
app = import_module("main").app
SCHEMA_PATH = REPOSITORY_ROOT / "openapi.json"


def main() -> None:
    schema = json.dumps(app.openapi(), indent=2, sort_keys=True)
    SCHEMA_PATH.write_text(f"{schema}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
