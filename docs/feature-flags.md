# Feature flags

Feature flags use the `FEATURE_` environment-variable prefix and are parsed
strictly at process startup. Accepted boolean values are `1`, `true`, `yes`,
`on`, `0`, `false`, `no`, and `off`. Invalid values stop startup rather than
silently selecting unexpected behavior.

## `FEATURE_STRICT_SETTLEMENT_VALIDATION`

Owner: Settlement API maintainers

Default: `false`

When enabled, settlement lines must reference an existing charge and have a
non-zero amount. Negative amounts are processor refund adjustments and are
accepted on both paths. The default preserves the legacy ingestion path while the
stricter validation is rolled out and monitored.

Rollout:

1. Enable the flag in development and staging.
2. Confirm processor files do not contain unknown charge IDs or zero amounts.
3. Enable it for production.
4. After one release with no rejected valid traffic, remove the legacy path
   and the flag in the same change.
