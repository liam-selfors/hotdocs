# License Scanner — Non-Functional Constraints

- **Determinism.** Same `gen/<component>/` content and the same reference
  corpus version MUST always produce the same `similarity_score` — required
  for cache-key correctness (`notes/initial-ideas.md`'s own D13), same as
  every other gate.
- **No model calls.** Pure hashing/comparison logic, same trust tier as
  `spec-linter`, `impact-analyzer`, and `cache-manager`.
- **Never silent.** A clean result is recorded with the same rigor as a
  flagged one, and a flagged-then-retried-clean history is never collapsed
  to the final state (`R-LICENSE-002`/`007`). A scan that checked nothing
  says so (`evaluated: false`), never passes as clean (`R-LICENSE-010`).
- **Fail closed.** A corpus the operator configured but that cannot be
  used blocks (`R-LICENSE-011`); only the absence of any corpus is allowed
  to pass, and it passes visibly.
- **Reference-corpus confidentiality.** The corpus of known-licensed-code
  fingerprints MAY itself be sensitive (e.g. proprietary code samples used
  only as hashes) — this component MUST only ever compare against
  precomputed hashes, never embed or expose the reference corpus's raw
  source in `LicenseScanResult` or logs.
