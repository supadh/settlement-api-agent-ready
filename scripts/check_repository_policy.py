import argparse
import re
from pathlib import Path

MAX_BYTES = 256 * 1024
MAX_TEXT_LINES = 500
TEXT_SUFFIXES = {".md", ".py", ".toml", ".yaml", ".yml"}
DEBT_MARKER_NAMES = ("TO" + "DO", "FIX" + "ME")
MARKER = re.compile(rf"\b(?:{'|'.join(DEBT_MARKER_NAMES)})\b")
TRACKED_MARKER = re.compile(rf"\b(?:{'|'.join(DEBT_MARKER_NAMES)})\((?:MER|GH)-\d+\):")


def check_file_limits(paths: list[Path]) -> list[str]:
    failures = []
    for path in paths:
        size = path.stat().st_size
        if size > MAX_BYTES:
            failures.append(f"{path}: {size} bytes exceeds {MAX_BYTES} bytes")
        if path.suffix in TEXT_SUFFIXES:
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            if line_count > MAX_TEXT_LINES:
                failures.append(f"{path}: {line_count} lines exceeds {MAX_TEXT_LINES}")
    return failures


def check_debt_markers(paths: list[Path]) -> list[str]:
    failures = []
    for path in paths:
        if path.suffix not in TEXT_SUFFIXES:
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if MARKER.search(line) and not TRACKED_MARKER.search(line):
                failures.append(
                    f"{path}:{line_number}: debt marker must include "
                    "TODO(MER-123): or FIXME(GH-123):"
                )
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("policy", choices=("file-limits", "debt-markers"))
    parser.add_argument("filenames", nargs="*")
    arguments = parser.parse_args()
    paths = [
        Path(filename) for filename in arguments.filenames if Path(filename).is_file()
    ]
    if arguments.policy == "file-limits":
        failures = check_file_limits(paths)
    else:
        failures = check_debt_markers(paths)

    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Repository policy passed: {arguments.policy}")


if __name__ == "__main__":
    main()
