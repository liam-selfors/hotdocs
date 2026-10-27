# Merge Tracker UI — Non-Functional Constraints

- **No backend computation.** Static page, DuckDB-WASM in the browser —
  same posture `docs-site-renderer` already established, applied
  here to a different data source. **Clarified by R-UI-006 (D16):** the
  local static-file server `serve` starts is not an exception to this —
  it serves literal file bytes only, computes nothing, and DuckDB-WASM
  still performs the actual query entirely client-side. This constraint
  was never about the transport a developer uses to open the page, only
  about where the query runs.
- **No network access from the rendered page.** Everything it queries is
  local (`.hotdocs/tracking/`, reached via `serve`'s loopback server,
  R-UI-006); it MUST NOT fetch anything remote.
- **Never the gate.** Nothing about this component's rendering, or
  whether a developer even has it open, affects any merge's outcome —
  same boundary `merge-tracker` itself observes (`SPEC_GUIDELINES.md`
  §1).
- **Graceful on an empty or missing tracking directory.** A fresh
  checkout with no merges run yet MUST render a clear empty state
  (R-UI-005), not an error — this is the common case for anyone just
  cloning the repo, not an edge case.
