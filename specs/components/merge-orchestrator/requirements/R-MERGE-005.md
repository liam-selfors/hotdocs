# R-MERGE-005

**R-MERGE-005** — **This is the best-of-k retry loop (D3), owned here.**
  If `verifier-orchestrator`'s verdict is `fail`, MUST call `generator`
  again with a new sample index, up to `k` total attempts (R-MERGE-016
  resolves `k`'s value), re-verifying each. The first sample whose verdict
  is `pass` MUST be kept; its sample index MUST be the one recorded for
  provenance (D3).

  Every retry call (every attempt after the first in the sequence) MUST
  pass `retry_feedback` to `generator`: the list of `R-id`s whose
  `requirement_results` entry (R-VERIFY-011) was `fail` on the
  **immediately preceding** attempt in this same sequence. This is a pure
  pass-through — `merge-orchestrator` MUST NOT inspect, filter, or
  otherwise interpret the failing `R-id` list beyond extracting it from
  the prior attempt's `VerificationReport` and handing it to `generator`
  unchanged. The first attempt in a sequence MUST NOT pass
  `retry_feedback` (there is no preceding attempt to derive it from).

  Feedback is deliberately **not accumulated** across more than one prior
  attempt — only the immediately preceding attempt's failures are passed,
  not a running union across the whole sequence. A requirement that failed
  two attempts ago and now passes should not keep showing up in feedback;
  carrying stale failures forward risks steering the model away from
  content it has already fixed.
