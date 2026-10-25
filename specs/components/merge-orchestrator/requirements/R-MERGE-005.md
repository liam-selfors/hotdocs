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

  Closes a gap `specs/decisions/D22.md` found and fixed: retrying only
  on verification failure meant `model_call_error` never triggered a
  retry at all (see `specs/decisions/D21.md` on why that's worse now
  that `generator` retries nothing itself).

  A retry whose **immediately preceding** attempt reached verification
  MUST pass `retry_feedback` to `generator`: the `R-id`s whose
  `requirement_results` entry (R-VERIFY-011) was `fail` on that attempt
  — a pure pass-through, never inspected or filtered. A retry whose
  immediately preceding attempt was instead a `model_call_error` MUST
  NOT pass `retry_feedback` — no `VerificationReport` exists to derive
  it from, so this retry is blind, same as the sequence's first attempt.
  Feedback is **not accumulated** across more than one prior attempt —
  only the immediately preceding attempt's failures count (rationale:
  `specs/decisions/D17.md`).
