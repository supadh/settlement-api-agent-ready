# Operations

## Monitoring and deployment impact

Set `GRAFANA_DASHBOARD_URL` in each deployed environment to the service
dashboard. Operators start there for request rate, errors, latency, health, and
reconciliation mismatch metrics. `APP_RELEASE` must contain the deployed image
tag so dashboards and Sentry group behavior by release.

Sentry is enabled only when `SENTRY_DSN` is set. Configure `SENTRY_ORG` and
`SENTRY_PROJECT`, install Sentry's GitHub integration, and enable automatic
issue creation for new high-severity regressions. This links errors to commits
and creates actionable repository issues without embedding credentials.

PostHog is enabled only when `POSTHOG_API_KEY` is set. The service emits:

- `settlement.charge_created`
- `settlement.refund_created`
- `settlement.reconciliation_requested`

Merchant identifiers are hashed before transmission. Card tokens, refund
reasons, and monetary values are not analytics properties.

Prometheus-compatible alert rules live in `ops/prometheus-alerts.yml`. Route
critical alerts to the on-call notification destination and warning alerts to
the settlement operations channel. Every alert links to a repository runbook.

## Profiling

Set `SENTRY_PROFILES_SAMPLE_RATE` to a value greater than zero only after
confirming the telemetry budget. Start at `0.05` in production. Profiling is
disabled by default and uses the same release/environment context as errors and
traces.
