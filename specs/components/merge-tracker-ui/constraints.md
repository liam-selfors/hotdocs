# Merge Tracker UI — Non-Functional Constraints

- **No server process.** Static page, DuckDB-WASM in the browser — same
  posture `docs-site-renderer` already established (D9), applied here to
  a different data source.
- **No network access from the rendered page.** Everything it queries is
  local (`.hotdocs/tracking/`); it MUST NOT fetch anything remote.
- **Never the gate.** Nothing about this component's rendering, or
  whether a developer even has it open, affects any merge's outcome —
  same boundary `merge-tracker` itself observes (`SPEC_GUIDELINES.md`
  §1).
- **Graceful on an empty or missing tracking directory.** A fresh
  checkout with no merges run yet MUST render a clear empty state
  (R-UI-005), not an error — this is the common case for anyone just
  cloning the repo, not an edge case.
