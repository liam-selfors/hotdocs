# R-LICENSE-003

**R-LICENSE-003** — Each reference-corpus entry MUST carry a declared
  **`risk_tier`** (`high` / `medium` / `low`). A notification to `VAR-COMPLIANCE-WEBHOOK-URL` MUST fire
  when **either** the match blocked the merge (R-LICENSE-001) **or** the
  matched entry's `risk_tier` is `high` — regardless of confidence in the
  latter case. Severity is never a function of the similarity score.
  Notification is independent of the merge outcome,
  including when a later retry (R-LICENSE-007) produces clean code. When `VAR-COMPLIANCE-WEBHOOK-URL` is
  absent, no notification is sent, but the record from R-LICENSE-002 still
  exists regardless.

  The webhook call itself MUST be attempted at most once, with no
  retry-with-backoff. A failure (network, auth, or
  timeout) MUST be caught and recorded as `notification_delivery_error`
  on the result, never retried, never raised, and never allowed to
  affect `blocked`. `notified` reflects whether a notification was *due*,
  computed from the preconditions above before any call, never whether
  it was delivered.
