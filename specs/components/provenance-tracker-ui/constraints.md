# Provenance Tracker UI — Non-Functional Constraints

- **All computation at build time, none at view time.** `render_tracker_ui`
  does every read once, in Python; the written page only renders data
  already inlined into it (`R-UI-001`, `D154`).
- **No network access from the rendered page.** It fetches nothing,
  local or remote, and references no external resource; it opens
  directly from `file://` (`R-UI-006`).
- **Never the gate.** Nothing about this component's output, or whether
  a developer ever builds it, affects any provenance check's outcome —
  the same boundary `provenance-tracker` itself observes (`D87`).
- **Graceful on a node with no provenance at all.** A fresh checkout
  with nothing yet `hotdocs generate`-d MUST render a clear "not yet
  attempted" state per component (`R-UI-005`), not an error — the
  common case for anyone just cloning the repo, not an edge case.
- **Deterministic.** The same `VerifyReport`, `corpus-graph.json`, and
  `.hotdocs/attempts/` contents MUST produce a byte-identical
  `index.html`: no timestamp, random id, or unordered iteration in the
  output.
