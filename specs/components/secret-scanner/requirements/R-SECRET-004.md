# R-SECRET-004

**R-SECRET-004** — A notification to `VAR-COMPLIANCE-WEBHOOK-URL` MUST
  fire when **either** a match blocked the merge (`R-SECRET-002`) **or**
  a match's `risk_tier` is `high`, the same orthogonal block/severity
  split as `license-scanner`'s `R-LICENSE-003`. It is independent of the
  merge outcome: a later clean scan never erases the flagged attempt's
  record (`D19`'s `.hotdocs/attempts/`, as `R-LICENSE-007`).
  The webhook call is attempted at most once, with no retry: a failure
  (network, auth, timeout) MUST be caught and recorded as
  `notification_delivery_error`, never retried, never raised, never
  affecting `flagged`. `notified` stays precondition-only.
