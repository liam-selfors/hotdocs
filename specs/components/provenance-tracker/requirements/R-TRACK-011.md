# R-TRACK-011

**R-TRACK-011** — `check_readiness` MUST resolve every dependency
  module (`provenance-checker`, `impact-analyzer`,
  `capability-scenario-verifier`) relative to the `repo_root` it was
  called with — from `<repo_root>/gen/<dependency-slug>/<module_name>.py`
  (flat) or `<repo_root>/gen/<dependency-slug>/<module_name>/__init__.py`
  (package) — never relative to this component's own file, and never
  trusting a prior `sys.modules` entry keyed by module name alone across
  two different `repo_root` calls in one process. This is the dynamic
  loading convention of `test-author`'s `R-AUTHOR-010`; a candidate that
  resolved from its own location loaded the real dependency instead of a
  test's isolated fake (`D111`).
