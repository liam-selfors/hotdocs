# R-TRACK-012

**R-TRACK-012** — `check_readiness` MUST read every field of a value a
  dependency returns (`provenance-checker`'s `ProvenanceCheckResult`,
  `SealedKey`, and `SealedCheckResult`, `impact-analyzer`'s
  `BlastRadiusReport` and each `impacted` entry,
  `capability-scenario-verifier`'s result) using dual dict-or-attribute
  access, never bare `.attr` alone (`D94`, `D121`).
