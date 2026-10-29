# R-VERIFY-013

**R-VERIFY-013** — Every dynamically loaded module (the component
  under test, `criterion-compiler`, `spec-bundle-assembler`, and any
  other dependency) MUST be cached, if at all, keyed by
  `(repo_root, module_name)` — never by `module_name` alone. A bare
  module-name key in `sys.modules` collides across two different
  `repo_root`s using the same component slug in the same process
  (every real verification call this component's own test suite
  makes uses slug `"foo"` against a fresh `tmp_path` each time), so a
  later call can silently reuse an earlier call's stale module.

  Found only once a real regenerated candidate's own interface-drift
  check (`R-VERIFY-004`) returned `false` for a fixture that
  renamed its one documented callable — confirmed, by calling the
  drift check directly outside the full `verify()` pipeline, that the
  check's own logic was correct; the stale module came from `load_
  component_module`'s own `sys.modules[module_name]` cache, populated
  by an *earlier, unrelated test* in the same pytest session that
  happened to use the same slug (`D120`) — the identical bug class
  `R-TRACK-011` already closed for `provenance-tracker`'s own loader.
