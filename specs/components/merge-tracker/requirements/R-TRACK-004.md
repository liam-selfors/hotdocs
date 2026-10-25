# R-TRACK-004

**R-TRACK-004** — This component MUST NOT read or depend on
  `merge-orchestrator`'s own `MergeResult` type. Per-component detail
  MUST be read from `provenance-writer`'s already-written manifests on
  disk (present in the working tree at the point this component runs,
  committed or not); merge-level facts (`changed_ids`, `block_reasons`,
  overall outcome) MUST be received as plain-value parameters, not as a
  reference to a `merge-orchestrator`-owned type.

  **This is what keeps the dependency graph acyclic:** `merge-orchestrator`
  depends on this component (it calls it); if this component also
  depended on `merge-orchestrator` (to know `MergeResult`'s shape), that
  would be a two-node cycle, which `spec-linter`'s `R-LINT-004` would
  correctly reject. `review-packet-builder` already established the
  precedent this requirement follows — needing some of the calling
  orchestrator's facts without depending on the orchestrator's own type,
  by reading already-produced sibling output from disk instead.
