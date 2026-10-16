# R-GEN-008

**R-GEN-008** — A model-call error (network, auth, rate-limit, timeout)
  MUST be reported as a distinct failure mode from "the model responded but
  the generated code may be wrong" — the former is what D10's
  fallback/halt logic reacts to; the latter is what `merge-orchestrator`'s
  best-of-k retry reacts to. Conflating them would misroute which recovery
  mechanism engages.
