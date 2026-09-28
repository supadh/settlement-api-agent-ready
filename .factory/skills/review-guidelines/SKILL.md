---
name: review-guidelines
description: Review Meridian settlement changes for monetary, reconciliation, testing, and logging risks.
---

# Meridian settlement review

Apply these checks when reviewing changes to this repository.

## Refund correctness

- Reject any refund path that validates only one refund against the original
  charge. The invariant is `sum(all refunds) <= original charge amount`.
- State the money consequence plainly, for example: three $60 refunds against a
  $100 charge pay out $180.

## Monetary and reconciliation correctness

- Reject floating-point arithmetic for money. All amounts are integer cents.
- Reject changes that allow reconciliation to produce a negative expected
  ledger balance.
- Require tests for matched, mismatched, refund, and settlement behavior.

## Sensitive data and operations

- Reject logs, analytics, fixtures, or responses that expose card tokens,
  secrets, or real personal data.
- Require structured logging instead of `print()`.
- Require tests for every new public function in `reconcile.py`.
- Require updates to OpenAPI, QA instructions, metrics, and runbooks when
  public or operational behavior changes.
