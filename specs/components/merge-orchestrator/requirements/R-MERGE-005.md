# R-MERGE-005

**R-MERGE-005** — MUST call `generator` **exactly once** per cache-miss,
  non-sealed component per merge attempt — no automatic retry loop
  (superseded `D3`/`D17`'s best-of-k mechanism; see `specs/decisions/
  D31.md`). If that one call does not produce a passing candidate —
  either because `generator` itself returned `model_call_error`
  (R-GEN-008, no candidate was ever produced to verify) or because a
  candidate was produced but `verifier-orchestrator`'s verdict on it was
  `fail` — the component is blocked (R-MERGE-006) for this merge attempt,
  full stop. Nothing here re-calls `generator` with a different seed or
  feeds anything back into a second attempt within the same merge.

  **This is a deliberate reversal, not an oversight.** `D17` explicitly
  considered and rejected dropping retry entirely, because a failure is
  frequently a generation miss on an otherwise-adequate spec, and losing
  the recovery path would push real spec-authoring overhead onto every
  transient miss. `D31` resolves that same concern differently: the
  recovery path is **not removed**, it moves outside this component
  entirely — re-running the merge (R-MERGE-018, unaffected by this
  requirement) is still free for every component that already passed,
  and gives a human a deliberate pause to look at *why* the one attempt
  failed (via `D32`'s per-attempt record) before deciding whether to
  just re-run unchanged or fix the spec first. A transient miss costs one
  conscious re-run instead of a silent, automatic one; a genuine spec gap
  gets a human's attention before the model is asked to guess again.
