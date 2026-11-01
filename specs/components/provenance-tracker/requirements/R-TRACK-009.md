# R-TRACK-009

**R-TRACK-009** — MUST expose `check_readiness(repo_root: Path,
  changed_ids: list[str] | None = None, model: str | None = None,
  seed: int = 0, llm_backend=None) -> VerifyReport` (`D88`/`D93`): given
  `changed_ids`, MUST call `impact-analyzer` to compute the blast
  radius and check `provenance-checker` for a hit for each component:
  call `provenance-checker`'s `current_provenance_key(component_id,
  repo_root)` and pass its `spec_bundle_hash` and `gate_versions`,
  unchanged, to `check_provenance` — never computing either value, or
  hit/miss logic, itself (`D163`). Given no `changed_ids` (or an empty list), MUST check every
  component in `specs/components/` the same way — the whole-corpus
  scope: every directory there holding a `component.md`, identified by
  that file's frontmatter `id`, never by re-deriving an id from the
  directory name.

  **MUST NOT call `component-gate-runner` for any component in
  scope, on a hit or a miss** (`D93`, reversing `D92`'s brief
  combination of generation into this check): generating new code is a
  deliberate, potentially expensive action a developer triggers by name
  with `hotdocs generate`, never a side effect `hotdocs verify` springs
  as a surprise. Since this half of the check is pure and read-only,
  nothing about ordering components against their own `depends_on`
  relationships matters here — unlike `hotdocs generate`, which a
  developer must still run in dependency order themselves across a
  multi-component change.

  A component whose check is a miss or whose hit carries a failing
  `verification_report`/blocking scan result is reported as not ready,
  never just a bare boolean: its `not_ready_reasons` entry names the
  component and which check failed — `verification`, `license_scan`,
  or `secret_scan` — and, for a failing `verification_report`, every
  `R-id` its `requirement_results` marks `"fail"`.

  **`impact-analyzer` MUST be loaded (imported/resolved) lazily, only
  at the point it is actually called, never eagerly at the top of
  `check_readiness` or in any setup step that runs regardless of
  scope** (`D98`): given no `changed_ids`, `impact-analyzer`'s own
  module is never loaded at all, not merely "called conditionally". `provenance-checker` is the one dependency
  genuinely needed by every scope and MAY be loaded unconditionally.

