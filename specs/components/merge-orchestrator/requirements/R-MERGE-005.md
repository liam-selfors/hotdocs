# R-MERGE-005

**R-MERGE-005** — **This is the best-of-k retry loop (D3), owned here.**
  If an attempt did not produce a passing candidate — either because
  `generator` itself returned `model_call_error` (R-GEN-008, no candidate
  was ever produced to verify) or because a candidate was produced but
  `verifier-orchestrator`'s verdict on it was `fail` — MUST call
  `generator` again with a new sample index, up to `k` total attempts
  (R-MERGE-016 resolves `k`'s value). The first sample whose verdict is
  `pass` MUST be kept; its sample index MUST be the one recorded for
  provenance (D3).

  **Closes a real gap:** retrying only on verification failure meant a
  `model_call_error` on attempt one had no verdict to be `fail`, so the
  trigger never fired and one transient hiccup exhausted `k` for nothing
  — a bigger problem now that `generator` does no retry of its own
  (R-GEN-011, D21) and best-of-k is the only cheap layer short of a full
  merge re-run (R-MERGE-018) that can absorb it.

  A retry whose **immediately preceding** attempt reached verification
  (produced a candidate `verifier-orchestrator` then failed) MUST pass
  `retry_feedback` to `generator`: the `R-id`s whose `requirement_results`
  entry (R-VERIFY-011) was `fail` on that attempt — a pure pass-through,
  never inspected, filtered, or interpreted beyond extraction from the
  prior `VerificationReport`. A retry whose immediately preceding attempt
  was instead a `model_call_error` MUST NOT pass `retry_feedback` — no
  `VerificationReport` exists to derive it from, so this retry is blind,
  same as the sequence's first attempt (also never passes it, for the
  same reason).

  Feedback is deliberately **not accumulated** across more than one prior
  attempt — only the immediately preceding attempt's failures are passed,
  not a running union across the whole sequence. A requirement that failed
  two attempts ago and now passes should not keep showing up in feedback;
  carrying stale failures forward risks steering the model away from
  content it has already fixed.
