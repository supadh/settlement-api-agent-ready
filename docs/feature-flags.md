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

## `FEATURE_HIGH_REFUND_FLAGGING`

Owner: Settlement API maintainers

Default: `false`

When enabled, `GET /merchants/{id}/reconciliation` adds a
`high_refund_charges` array listing charges whose cumulative refunds exceed
90% of the original amount (strictly greater than 90%; charges refunded
exactly 90% are not flagged). Entries are ordered as the charges iterate and
contain `charge_id`, `charge_amount_cents`, `refunded_cents`, and
`refund_ratio_percent` (integer floor of the ratio). When the flag is off the
response contains no `high_refund_charges` key.

Rollout:

1. Enable the flag in development and staging.
2. Confirm the flagged list matches the settlements team's expectations on
   known refund-abuse cases.
3. Enable it for production and let callers adopt the new field.
4. After consumers have migrated to the new field, remove the flag and emit
   `high_refund_charges` unconditionally in the same change.
