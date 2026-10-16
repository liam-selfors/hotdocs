# R-LICENSE-003

**R-LICENSE-003** — Each reference-corpus entry MUST carry a declared
  **`risk_tier`** (`high` / `medium` / `low` — reflecting the matched
  entry's license family: e.g. `high` for strong-copyleft or
  unlicensed/proprietary sources, `medium` for weak-copyleft, `low` for
  permissive). A notification to `VAR-COMPLIANCE-WEBHOOK-URL` MUST fire
  when **either** the match blocked the merge (R-LICENSE-001) **or** the
  matched entry's `risk_tier` is `high` — regardless of confidence in the
  latter case. Severity is deliberately **not** a function of the
  similarity score: block answers "are we confident," `risk_tier` answers
  "how bad if real," and conflating the two would both over-notify on
  confident-but-low-risk matches and under-notify on uncertain-but-
  high-risk ones. Notification is independent of the merge outcome,
  including when a later retry (R-LICENSE-007) produces clean code, so an
  auto-resolved flag still gets seen. When `VAR-COMPLIANCE-WEBHOOK-URL` is
  absent, no notification is sent, but the record from R-LICENSE-002 still
  exists regardless.
