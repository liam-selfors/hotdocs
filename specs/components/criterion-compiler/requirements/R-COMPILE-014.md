# R-COMPILE-014

**R-COMPILE-014** — Any component depending on this one directly (not
  via an injected callable — `verifier-orchestrator`'s `R-VERIFY-001`,
  `capability-scenario-verifier`'s `R-SCENARIO-001`) MUST import
  `criterion_compiler` lazily, at call time, resolved relative to its
  own `repo_root` parameter — never a static top-level
  `import criterion_compiler` statement, which only works by accident
  of load order and breaks across callers given different `repo_root`
  values (`D83`).

  The caller MUST try a plain `import criterion_compiler` first (the
  seam for a test to pre-register a fake in `sys.modules`), then on
  failure add `repo_root / "pipeline" / "criterion-compiler"` and
  `repo_root / "gen" / "criterion-compiler"`, in that order, to
  `sys.path` before retrying — `pipeline/` first since this component
  is `sealed: true` and lives there; `gen/` as a forward-compatible
  fallback.
