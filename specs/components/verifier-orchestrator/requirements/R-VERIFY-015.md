# R-VERIFY-015

**R-VERIFY-015** — The module MUST define `GATE_VERSION`, currently
  `"verifier-orchestrator@3.5.0"`, readable without calling `verify`.
  Any change to the mutation sites, the threshold, the timeout rule or
  how a criterion's `kind` is dispatched MUST bump it here, since a
  provenance hit reuses this gate's verdict only while it is unchanged
  (`D163`).
