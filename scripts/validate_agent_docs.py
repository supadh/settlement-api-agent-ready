from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AGENT_GUIDE = REPOSITORY_ROOT / "AGENTS.md"
SKILL = REPOSITORY_ROOT / ".factory" / "skills" / "review-guidelines" / "SKILL.md"


def require_text(path: Path, snippets: tuple[str, ...]) -> None:
    content = path.read_text(encoding="utf-8")
    for snippet in snippets:
        if snippet not in content:
            raise RuntimeError(f"{path} is missing required text: {snippet}")


def main() -> None:
    require_text(
        AGENT_GUIDE,
        (
            "python -m pip install -r requirements-dev.txt",
            "python -m pytest tests",
            "python scripts/generate_openapi.py",
            "docs/qa.md",
            "docs/architecture.md",
        ),
    )
    require_text(
        SKILL,
        (
            "name: review-guidelines",
            "description:",
            "Refund correctness",
            "Sensitive data and operations",
        ),
    )
    for relative_path in (
        "requirements-dev.txt",
        "docs/qa.md",
        "docs/architecture.md",
        "scripts/generate_openapi.py",
    ):
        if not (REPOSITORY_ROOT / relative_path).exists():
            raise RuntimeError(f"Documented path does not exist: {relative_path}")
    print("Agent documentation is internally consistent")


if __name__ == "__main__":
    main()
