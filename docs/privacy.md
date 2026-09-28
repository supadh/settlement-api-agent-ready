# Privacy and sensitive-data handling

## Data classification

| Class | Examples | Handling |
| --- | --- | --- |
| Restricted | card tokens, authorization headers, cookies, API keys | Accept only when needed, never persist or return, redact from logs |
| Sensitive | merchant identifiers, names, email, phone, address, refund reason | Limit to the settlement purpose, redact from logs, restrict exports |
| Operational | request IDs, counts, timings, release names | May appear in logs and metrics |

Card tokens must be processor-issued tokens, not primary account numbers. The
service uses a token only while recording a charge and immediately discards it.
It never stores or returns that token. Observability hashes merchant identifiers
and excludes token, reason, and monetary fields.

## Secrets

Local development can use uncommitted environment variables. Deployed
environments must inject `SENTRY_DSN`, `POSTHOG_API_KEY`, and `ADMIN_API_KEY`
from their secret manager. Each secret also supports a mounted file through the
corresponding `_FILE` variable. Configure the direct value or file, never both.
Do not place a live value in `.env.example`, GitHub variables, logs, or images.

## Retention, export, and deletion

`DATA_RETENTION_DAYS` defaults to 30. Records older than the configured period
are purged with dependent refunds and settlement lines at request boundaries.
All records are also erased whenever this in-memory service restarts.

Authorized operators can use the hidden admin endpoints with `X-Admin-Key`:

```text
GET    /admin/privacy/merchants/{merchant_id}
DELETE /admin/privacy/merchants/{merchant_id}
```

The export contains all records associated with that merchant and no card
tokens. Deletion cascades through charges, refunds, and settlement lines.
Without `ADMIN_API_KEY` or `ADMIN_API_KEY_FILE`, both endpoints return 503.
Production operators must verify the requester, record the request outside this
service, use TLS, and deliver exports through an approved secure channel.

The production container disables Uvicorn access logs because resource paths
can contain merchant identifiers. Application logs use route templates and a
recursive allowlist-independent redactor. Sentry drops request payloads and
request URLs before transmission in addition to disabling default PII.
