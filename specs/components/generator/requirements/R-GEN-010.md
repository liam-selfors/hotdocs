# R-GEN-010

**R-GEN-010** — The model call MAY optionally receive `retry_feedback` — a
  list of `R-id`s that a **prior attempt within the same best-of-k retry
  sequence** (same `spec_bundle_hash`, same `merge-orchestrator` call,
  different seed) failed to satisfy, per `verifier-orchestrator`'s
  `requirement_results` (R-VERIFY-011). When present, it MUST be included
  as its own clearly distinguished context section, never merged with or
  indistinguishable from the `SpecBundle`'s own fields — the same
  clear-separation discipline R-GEN-002 already established for
  `hint_code`, applied here to a different kind of extra context.

  `retry_feedback` MUST contain **only** `R-id`s — never Gherkin text,
  `rationale`, expected/actual values, or any other acceptance-criterion
  content. This boundary is load-bearing, not a style preference: it is
  the entire reason this mechanism doesn't reopen `spec-bundle-assembler`'s
  R-ASSEMBLE-001 exclusion of `acceptance/` from what a generation model
  ever sees. A list of failed `R-id`s discloses nothing beyond "a prior
  attempt didn't satisfy text you already have" — the requirements
  themselves are already in the bundle via `requirements/`.

  `generator` MUST NOT be the component responsible for deciding *whether*
  to use `retry_feedback` on a given attempt — that is `merge-orchestrator`'s
  retry-loop decision (R-MERGE-005). `generator` only ever does one thing
  with it when present: include it, scoped exactly as described, in that
  one call's prompt.
