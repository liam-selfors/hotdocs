# R-SECRET-004

**R-SECRET-004** — A notification to `VAR-COMPLIANCE-WEBHOOK-URL` MUST
  fire when **either** a match blocked the merge (`R-SECRET-002`) **or**
  a match's `risk_tier` is `high` (an allowed finding is no match). It writes no `.hotdocs/` attempt record (`D19`); a later
  clean scan never un-notifies. The webhook
  call is attempted at most once: a failure (network, auth, timeout)
  MUST be caught and recorded as `notification_delivery_error`, never
  raised, never affecting `flagged`. `notified` stays precondition-only.
