# R-TRACK-009

**R-TRACK-009** — MUST expose `check_readiness(repo_root: Path,
  changed_ids: list[str] | None = None, model: str | None = None,
  seed: int = 0, llm_backend=None) -> VerifyReport` (`D88`/`D93`): given `changed_ids`, MUST call `impact-analyzer` to compute the blast
  radius and check each component, unless its report's
  `precondition_error` is not null: the scope is then unknown, so no
  component or capability is checked, `ready` is false, and
  `not_ready_reasons` is exactly
  `["blast radius unavailable: <precondition_error>"]`; given none (or an empty list), MUST
  check every directory under `specs/components/` holding a
  `component.md`, identified by that file's frontmatter `id` (parsed
  with `yaml.safe_load`, never by hand), never by the directory name.

  **Each component is checked by exactly one of two paths, chosen by
  `provenance-checker`'s `current_sealed_key(component_id, repo_root)`**
  (`D170`). If it returns `None`, call `current_provenance_key(component_id,
  repo_root)` and pass its `spec_bundle_hash` and `gate_versions`,
  unchanged, to `check_provenance` — never computing either value or the
  hit/miss logic itself (`D163`). If it returns a key, the component is
  sealed: call `check_sealed_provenance(component_id, repo_root)` instead,
  and treat `hit` as the whole verdict — a sealed component's license and
  secret scans are not part of it. Its `components` entry is the
  `SealedCheckResult` verbatim, and a miss is reported as
  `<id>: sealed provenance <reason> — run hotdocs generate <id>`.

  **MUST NOT call `component-gate-runner` for any component, on a hit or
  a miss** (`D93`).

  A non-sealed component whose check is a miss, or whose hit carries a
  failing `verification_report` or a `license_scan` whose `blocked` is
  true, is not ready, never a bare boolean: its `not_ready_reasons`
  entry names the component and which check failed — `verification` or
  `license_scan` — and, for a failing report, every `R-id` its
  `requirement_results` marks `"fail"`. Its stored `secret_scan` is
  never read (`R-TRACK-016`).

  **`impact-analyzer` MUST be loaded lazily, only at the point it is
  called** (`D98`): given no `changed_ids`, its module is never loaded at
  all. `provenance-checker` is needed by every scope and MAY be loaded
  unconditionally.
