# Runbook: reconciliation mismatch spike

1. Open the dashboard configured by `GRAFANA_DASHBOARD_URL` and identify the
   affected release and time window.
2. Use request IDs to correlate mismatch metrics, structured logs, and Sentry.
3. Confirm settlement lines reference valid charges and inspect whether strict
   settlement validation is enabled.
4. Separate expected refund mismatches from true discrepancies. A mismatch whose
   `difference_cents` equals `refunded_cents` is a partial refund still
   awaiting its negative processor adjustment line; it clears once the next
   settlement file is ingested. Escalate only if it persists past that cycle.
5. Do not log or paste card tokens into incident notes.
6. Pause settlement ingestion if incorrect payouts are possible.
7. Reconcile affected merchants from trusted processor source data, then record
   the correction and follow-up owner.
