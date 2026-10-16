# R-SECRET-004

**R-SECRET-004** — A notification to `VAR-COMPLIANCE-WEBHOOK-URL` MUST
  fire when **either** a match blocked the merge (R-SECRET-002) **or** the
  matched rule's `risk_tier` is `high` — mirroring `license-scanner`'s
  R-LICENSE-003 exactly, the same orthogonal block/severity split, not a
  second, independently-designed mechanism. Independent of the merge
  outcome, including when a retry later scans clean.
