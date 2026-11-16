# R-DRIFT-004

**R-DRIFT-004** — `graph-query-engine` (and any other dependency this
  component loads dynamically) MUST be resolved relative to the
  `repo_root` actually passed to `find_decision_drift`/
  `find_decision_impact`, never relative to this component's own
  `__file__` location while `repo_root` has it — the identical bug class `R-TRACK-011`/
  `R-VERIFY-013` already closed for `provenance-tracker` and
  `verifier-orchestrator`: a verification harness runs this candidate
  from one location while exercising it against a *different*,
  test-controlled `repo_root`, so a `__file__`-relative resolution
  silently finds the real sibling dependency instead of the test's own
  fake, defeating the fake entirely without ever raising.

  **Literal worked snippet, not prose alone** (`R-AUTHOR-010`): resolve
  `Path(repo_root) / "gen" / "graph-query-engine"` and load
  `graph_query_engine.py` (flat) or `graph_query_engine/__init__.py`
  (package) from it; only when that directory does not exist, use the
  same path under the tool root, the parent of the nearest directory
  named `gen` above this module's own `__file__` (`D199`). Cache the
  loaded module keyed by `(str(repo_root), module_name)`, never by bare
  module name alone.

  Found via a real cold-generation attempt (`D134`): a candidate
  resolved `graph_query_engine` from its own `__file__`'s location,
  which — inside this driver's own sandboxed verification — happens to
  coincidentally also contain a real copy of `graph-query-engine`,
  silently loading that instead of the test's fake and never calling
  it at all, masked as a behavioral assertion failure rather than an
  obvious crash.
