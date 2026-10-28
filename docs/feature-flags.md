# Feature flags

Feature flags use the `FEATURE_` environment-variable prefix and are parsed
strictly at process startup. Accepted boolean values are `1`, `true`, `yes`,
`on`, `0`, `false`, `no`, and `off`. Invalid values stop startup rather than
silently selecting unexpected behavior.

## `FEATURE_STRICT_SETTLEMENT_VALIDATION`

Owner: Settlement API maintainers

Default: `false`

When enabled, settlement lines must reference an existing charge and have a
positive amount. The default preserves the legacy ingestion path while the
stricter validation is rolled out and monitored.

Rollout:

1. Enable the flag in development and staging.
2. Confirm processor files do not contain unknown charge IDs or non-positive
   amounts.
3. Enable it for production.
4. After one release with no rejected valid traffic, remove the legacy path
   and the flag in the same change.

## `FEATURE_ONCHAIN_SETTLEMENT`

Owner: Settlement API maintainers

Default: `false`

When enabled, `POST /settlements/onchain` can originate payouts of recorded
charges to a Base wallet in USDC through the Coinbase adapter. The endpoint
requires an `Idempotency-Key` header so retries never double-payout. When
disabled, the endpoint returns `503` and never contacts Coinbase.

Rollout:

1. Enable the flag in development and staging against a Coinbase test wallet.
2. Confirm onchain settlement lines reconcile against processor reports with
   matching amounts.
3. Enable it for production.
4. Once payouts are durably recorded (the current in-memory ledger is
   process-local), remove the flag and the guard in the same change.
