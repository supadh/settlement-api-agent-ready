# Agent guide

## Purpose and architecture

This repository contains one FastAPI service for recording charges, refunds,
processor settlement lines, and merchant reconciliation. HTTP routes live in
`main.py`, domain state and calculations live in `reconcile.py`, environment
feature flags live in `feature_flags.py`, and observability adapters live in
`logging_config.py`, `metrics.py`, and `observability.py`.

Read `docs/architecture.md` before changing service boundaries or persistence.
The current in-memory ledger is process-local and supports only one worker.

## Setup and run

Use Python 3.12. From a fresh clone:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Run the development server:

```bash
uvicorn main:app --reload
```

No authentication, database, or external local service is currently required.
Never use real card tokens, merchant data, API keys, or personal data in local
development.

## Validation

Run the complete tests:

```bash
python -m pytest tests
```

Run repository quality and maintainability gates:

```bash
pre-commit run --all-files
```

This runs Ruff lint and formatting checks, strict mypy, file-size and
debt-marker policies, complexity analysis, dead/duplicate-code analysis, and
unused-dependency detection.

Verify bounded unit-test collection:

```bash
python -m pytest --collect-only tests/test_reconcile.py
```

Regenerate the API schema after changing routes or request models:

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/generate_openapi.py
git diff --exit-code -- openapi.json
```

Follow `docs/qa.md` for a live end-to-end API exercise. CI runs these checks and
retains test timing output.

## Development conventions

- Use `snake_case` for functions and variables, `PascalCase` for classes, and
  `UPPER_SNAKE_CASE` for constants.
- Keep monetary values as integer cents. Never introduce floating-point money.
- Preserve the invariant that total refunds cannot exceed the original charge.
- Keep HTTP concerns in `main.py` and domain calculations in `reconcile.py`.
- Add tests for every public behavior change and isolate the in-memory ledger.
- Use structured logs. Never use `print()` or log request bodies, card tokens,
  secrets, refund reasons, or raw merchant identifiers.
- Add environment switches through `feature_flags.py`; document ownership,
  default behavior, rollout, and removal in `docs/feature-flags.md`.
- Update `openapi.json`, architecture, QA, runbooks, and release instructions
  when their behavior changes.

## Workflow

Use the Linear **payment-gateway-settlement** project for implementation tracking.
Link pull requests to the relevant MER issue and GitHub coordination issue #1.
Use conventional commit subjects so Release Please generates useful notes.
Do not mark remotely validated tasks complete until CI, review, deployment, or
hosted integration evidence exists.
