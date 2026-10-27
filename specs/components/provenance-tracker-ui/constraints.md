# Provenance Tracker UI — Non-Functional Constraints

- **No backend computation.** Static page, DuckDB-WASM in the browser —
  same posture `docs-site-renderer` already established, applied here
  to a graph-shaped data source. **Clarified by R-UI-006 (D16):** the
  local static-file server `serve` starts is not an exception to this —
  it serves literal file bytes only, computes nothing, and DuckDB-WASM
  still performs every query entirely client-side.
- **No network access from the rendered page.** Everything it queries
  is local (`corpus-graph.json`, `.hotdocs/attempts/`, reached via
  `serve`'s loopback server, R-UI-006); it MUST NOT fetch anything
  remote.
- **Never the gate.** Nothing about this component's rendering, or
  whether a developer even has it open, affects any provenance check's
  outcome — same boundary `provenance-tracker` itself observes (`D87`).
- **Graceful on a node with no provenance at all.** A fresh checkout
  with nothing yet `hotdocs generate`-d MUST render a clear "not yet
  attempted" state per node (R-UI-005), not an error — this is the
  common case for anyone just cloning the repo, not an edge case.
