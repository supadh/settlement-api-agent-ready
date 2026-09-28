import subprocess
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_IGNORED_PATHS = (
    ".env",
    ".env.production",
    ".venv/bin/python",
    "__pycache__/module.pyc",
    ".idea/workspace.xml",
    ".vscode/settings.json",
    ".DS_Store",
    "build/package.whl",
    "dist/package.whl",
    "node_modules/package/index.js",
)


def is_ignored(path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", path],
        cwd=REPOSITORY_ROOT,
        check=False,
    )
    return result.returncode == 0


def main() -> None:
    failures = [path for path in EXPECTED_IGNORED_PATHS if not is_ignored(path)]
    if failures:
        raise RuntimeError(f"Expected ignored paths: {', '.join(failures)}")
    if is_ignored(".env.example"):
        raise RuntimeError(".env.example must remain committable")

    config = yaml.safe_load(
        (REPOSITORY_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    )
    updates = config.get("updates", [])
    if not updates:
        raise RuntimeError("Dependabot must configure dependency ecosystems")
    for update in updates:
        if update.get("cooldown", {}).get("default-days") != 7:
            ecosystem = update.get("package-ecosystem", "unknown")
            raise RuntimeError(f"{ecosystem} must retain a 7-day cooldown")
    print("Supply-chain policy is valid")


if __name__ == "__main__":
    main()
