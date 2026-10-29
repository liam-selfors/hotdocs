# R-TRACK-011

**R-TRACK-011** — `check_readiness` MUST resolve every dependency
  module (`provenance-checker`, `impact-analyzer`,
  `capability-scenario-verifier`) relative to the `repo_root`
  parameter it was called with — from
  `<repo_root>/gen/<dependency-slug>/<module_name>.py` (flat) or
  `<repo_root>/gen/<dependency-slug>/<module_name>/__init__.py`
  (package) — never relative to this component's own file location,
  and never trusting a prior
  `sys.modules` cache entry keyed by module name alone across two
  different `repo_root` calls in the same process. Mirrors the
  dynamic, `repo_root`-relative loading convention `test-author`'s own
  `R-AUTHOR-010` already documents and relies on for writing a fake
  dependency — this component is the first real one where that
  reliance was actually exercised for real.

  **Found only once a real `generated-test` for `AC-TRACK-009` faked
  `impact-analyzer` under an isolated `repo_root`** (`D111`): the real
  candidate's `_load_gen_module` resolved `_GEN_ROOT` from
  `Path(__file__).resolve().parent.parent` — this component's own
  on-disk location, not its `repo_root` argument — so it loaded the
  real, already-built `impact-analyzer` instead of the test's fake one,
  entirely defeating the fixture's isolation. This exact file-relative
  pattern already exists, pre-session, in `impact-analyzer`'s own
  dependency loader — out of scope to fix here, tracked separately —
  and the candidate evidently copied it as a plausible precedent.
