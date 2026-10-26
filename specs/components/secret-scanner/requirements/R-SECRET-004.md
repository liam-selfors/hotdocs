# R-SECRET-004

**R-SECRET-004** — A notification to `VAR-COMPLIANCE-WEBHOOK-URL` MUST
  fire when **either** a match blocked the merge (R-SECRET-002) **or** the
  matched rule's `risk_tier` is `high` — mirroring `license-scanner`'s
  R-LICENSE-003 exactly, the same orthogonal block/severity split, not a
  second, independently-designed mechanism. Independent of the merge
  outcome, including when a later merge attempt (`D31`) scans clean —
  mirroring `license-scanner`'s `R-LICENSE-007` exactly: the original
  flagged attempt's record (`D32`'s `.hotdocs/attempts/`) is never erased
  just because a subsequent attempt came back clean.

  The webhook call itself MUST be attempted at most once, with no
  retry-with-backoff, mirroring `license-scanner`'s `R-LICENSE-003`
  exactly: a failure (network, auth, or timeout) MUST be caught and
  recorded as `notification_delivery_error` on the result, never
  retried, never raised, and never allowed to affect `flagged`.
  `notified` stays precondition-only, unaffected by delivery outcome.
