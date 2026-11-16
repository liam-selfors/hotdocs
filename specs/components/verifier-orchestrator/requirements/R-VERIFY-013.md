# R-VERIFY-013

**R-VERIFY-013** — Every dynamically loaded module (the component
  under test, `criterion-compiler`, `spec-bundle-assembler`, and any
  other dependency) MUST be cached, if at all, keyed by
  `(repo_root, module_name)` — never by `module_name` alone. A bare
  module-name key collides across two different `repo_root`s using the
  same component slug in one process (this component's own tests use
  slug `"foo"` against a fresh `tmp_path` each time), so a later call
  could silently reuse an earlier call's stale module (`D120`; the same
  bug class `R-TRACK-011` closed for `provenance-tracker`).
