# R-DRIFT-004

**R-DRIFT-004** — `graph-query-engine` (and any other dependency this
  component loads dynamically) MUST be resolved relative to the
  `repo_root` actually passed to `find_decision_drift`/
  `find_decision_impact`, never relative to this component's own
  `__file__` location while `repo_root` has it — a test passes a
  `repo_root` holding fakes.

  Resolve
  `Path(repo_root) / "gen" / "graph-query-engine"` and load
  `graph_query_engine.py` (flat) or `graph_query_engine/__init__.py`
  (package) from it; only when that directory does not exist, use the
  same path under the tool root, the parent of the nearest directory
  named `gen` above this module's own `__file__` (`D199`). Cache the
  loaded module keyed by `(str(repo_root), module_name)`, never by bare
  module name alone.
