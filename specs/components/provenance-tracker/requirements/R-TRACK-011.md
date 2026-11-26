# R-TRACK-011

**R-TRACK-011** — `check_readiness` MUST resolve every dependency
  module (`provenance-checker`, `impact-analyzer`,
  `capability-scenario-verifier`, `secret-scanner`) relative to the `repo_root` it was
  called with — from `<repo_root>/gen/<dependency-slug>/<module_name>.py`
  (flat) or `<repo_root>/gen/<dependency-slug>/<module_name>/__init__.py`
  (package), or the tool root's when absent (`D199`); never trusting a prior `sys.modules` entry keyed by module name alone across
  two different `repo_root` calls in one process (`D111`).
