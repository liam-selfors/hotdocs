# R-VERIFY-015

**R-VERIFY-015** — The module MUST define `GATE_VERSION`, currently
  `"verifier-orchestrator@2.0.0"`, readable without calling `verify`.
  Any change to the mutation operators, the mutation threshold, the
  timeout rule, or how a criterion's `kind` is dispatched MUST bump it
  in this requirement, since a provenance hit reuses this gate's
  verdict only while its version is unchanged (`D163`).
