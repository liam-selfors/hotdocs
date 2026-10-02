---
id: comp-license-scanner-constraints
title: License Scanner — Non-Functional Constraints
status: draft
owners: [pipeline-team]
---

# License Scanner — Non-Functional Constraints

- **Determinism.** Same `gen/<component>/` content and the same reference
  corpus version MUST always produce the same `similarity_score` — required
  for cache-key correctness (D13), same as every other gate.
- **No model calls.** Pure hashing/comparison logic, same trust tier as
  `spec-linter`, `impact-analyzer`, and `cache-manager`.
- **Never silent.** Per R-LICENSE-002/007 — a clean result is recorded with
  the same rigor as a flagged one, and a flagged-then-retried-clean history
  is never collapsed down to just the final state.
- **Reference-corpus confidentiality.** The corpus of known-licensed-code
  fingerprints MAY itself be sensitive (e.g. proprietary code samples used
  only as hashes) — this component MUST only ever compare against
  precomputed hashes, never embed or expose the reference corpus's raw
  source in `LicenseScanResult` or logs.
