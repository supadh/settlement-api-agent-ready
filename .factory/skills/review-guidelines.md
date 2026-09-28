<!-- .factory/skills/review-guidelines/SKILL.md -->

Additional checks for this codebase (settlement reconciliation, Meridian Pay):

**Refund correctness**
- Flag any refund path that validates a single refund against the original
  charge amount without accounting for refunds already issued against that
  charge. A sequence of individually-valid partial refunds that sums above the
  charge total is a defect, not an edge case.
- The invariant is: sum(all refunds for a charge) <= original charge amount.
- State the money consequence in plain language, not just the missing check.
  Write "three $60 refunds against a $100 charge pay out $180" rather than
  "add cumulative validation."

**Monetary types**
- Flag any float arithmetic introduced on a monetary value. All amounts are
  integer cents.

**Reconciliation coherence**
- Flag any change that allows reconcile_merchant to compute a negative expected
  balance. A negative expectation means the ledger has already lost the argument.

**General**
- Flag new public functions in reconcile.py without corresponding tests.
- Flag print() used where structured logging belongs.
