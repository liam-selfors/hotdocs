# Impact Analyzer — Non-Functional Constraints

- **Determinism.** Same `(changed_ids, corpus state)` input MUST always
  produce byte-identical output. Required for D13's cache-key correctness,
  same as `spec-linter`. DuckDB queries are themselves pure functions of
  their input tables (R-IMPACT-009) — this property is a consequence of
  the engine choice, not something layered on top of it afterward.
- **Performance.** Computing blast radius for a single-digit number of
  changed ids MUST complete in well under 1 second against a corpus with
  hundreds of components — it is a graph traversal, not a search, and must
  not become a merge-latency bottleneck (D13). An embedded analytical
  engine built for exactly this shape of query is expected to clear this
  bar comfortably; this constraint does not relax just because the engine
  changed.
- **No network access, no model calls.** Pure graph logic over the already-
  validated corpus graph `spec-linter` produces, now via DuckDB's `yaml`
  and `duckpgq` extensions (both embedded, local, no network dependency —
  `specs/architecture/graph-query-engine.md`) rather than bespoke
  traversal code.
- **Fail closed, not best-effort.** Per R-IMPACT-007, an invalid corpus graph
  MUST produce an explicit precondition error, never a partial or
  silently-wrong blast radius — an under-computed blast radius here directly
  threatens `P-ZERO-EDIT` (a component that needed regeneration silently
  not getting it).
