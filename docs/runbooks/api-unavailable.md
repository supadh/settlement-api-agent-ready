# Runbook: API unavailable or high error rate

1. Open the dashboard configured by `GRAFANA_DASHBOARD_URL`.
2. Confirm `/health` and `/ready` status, request rate, latency, and 5xx rate.
3. Compare the first failing request with the latest deployment annotation and
   `APP_RELEASE`.
4. Open the matching Sentry issue using its request ID and release.
5. If the release caused the failure, follow `docs/releases.md` to roll forward
   or redeploy the last known-good immutable image.
6. Record impact, timestamps, release, mitigation, and follow-up owner.
