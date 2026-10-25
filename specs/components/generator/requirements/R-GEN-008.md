# R-GEN-008

**R-GEN-008** — A model-call error (network, auth, rate-limit, timeout)
  MUST be reported as a distinct failure mode from "the model responded but
  the generated code may be wrong" — the former is what D10's single-model
  halt posture and a subsequent merge re-run (R-MERGE-017) react to; the
  latter is what `merge-orchestrator`'s best-of-k retry reacts to.
  Conflating them would misroute which recovery mechanism engages.
