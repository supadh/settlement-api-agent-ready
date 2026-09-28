# Meridian Pay Settlement API

## Local setup

Create an isolated environment and install the pinned development dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

No secrets are required for local development. The variables in `.env.example`
are safe development defaults. Export them before starting the service if you
want to override a feature flag.

Start the server:

```bash
uvicorn main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

Follow [`docs/qa.md`](docs/qa.md) to run a complete interactive smoke test
against the live API.

## Development container

Open the repository in VS Code and choose **Dev Containers: Reopen in
Container**. The image installs the pinned runtime and development dependencies,
forwards port 8000, and verifies pytest test collection after creation.

## Quality checks

Run the same pinned checks locally and in CI:

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy .
pre-commit run --all-files
pytest
```

Ruff enforces imports, naming, correctness, modernization, and formatting.
mypy runs in strict mode across the application, scripts, and tests.
