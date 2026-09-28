# Service architecture

Meridian Settlement API is a single-process FastAPI service. It exposes charge,
refund, settlement-line, and merchant-reconciliation endpoints. Domain logic
lives in `reconcile.py`; HTTP validation and error translation live in
`main.py`; feature configuration lives in `feature_flags.py`.
`privacy.py` owns retention and admin authorization, while `secret_config.py`
supports environment and mounted-file secret injection.

The current persistence layer is deliberately in-memory. `charges`, `refunds`,
and `settlement_lines` are process-local collections. They are lost on restart
and are not shared between workers, so the service must run as one worker until
a durable store replaces them.

```mermaid
flowchart LR
    Client[Merchant or processor client] --> API[FastAPI routes]
    API --> Flags[Environment-backed feature flags]
    API --> Privacy[Retention and privacy controls]
    API --> Domain[Reconciliation domain functions]
    Domain --> Charges[(In-memory charges)]
    Domain --> Refunds[(In-memory refunds)]
    Domain --> Lines[(In-memory settlement lines)]
    Domain --> API
    API --> Client
```

## Reconciliation flow

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant Ledger as In-memory ledger

    Client->>API: POST /charges
    API->>Ledger: Store charge
    Client->>API: POST /settlement-lines
    API->>Ledger: Store processor line
    Client->>API: GET /merchants/{id}/reconciliation
    API->>Ledger: Read merchant charges, refunds, and lines
    Ledger-->>API: Matched and mismatched totals
    API-->>Client: Reconciliation result
```

## External dependencies

The running service calls no database. Optional Sentry and PostHog adapters are
disabled unless credentials are configured. Runtime dependencies are pinned in
`requirements.txt`. GitHub Actions provides CI, security scanning, release
automation, image publication, and automated Droid review.

The committed `openapi.json` is generated from the FastAPI application with:

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/generate_openapi.py
```
