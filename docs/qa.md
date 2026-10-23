# Interactive QA

The local service has no authentication gate. Use synthetic values only; never
send real card tokens or merchant data to a development instance.

## Start the service

From a fresh clone:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
set -a && source .env && set +a
uvicorn main:app --host 127.0.0.1 --port 8000
```

No database or other local service is required. Leave this terminal running.

## Exercise the API

In another terminal:

```bash
source .venv/bin/activate
python scripts/smoke_test.py --base-url http://127.0.0.1:8000
```

The script waits for the API, creates a synthetic charge, loads a matching
settlement line, and confirms the charge is reported as matched. It then issues
a partial refund, loads the processor's negative refund adjustment line for the
same charge, and confirms the charge reconciles as matched again at the reduced
ledger amount. It exits successfully only when both checks pass. Expected
output:

```text
Interactive API smoke test passed
```

Open <http://127.0.0.1:8000/docs> to inspect and exercise individual endpoints.
Stop the server with `Ctrl-C`.
