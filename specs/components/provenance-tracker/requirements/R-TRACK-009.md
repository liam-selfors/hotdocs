# R-TRACK-009

**R-TRACK-009** — MUST expose `check_readiness(repo_root: Path,
  changed_ids: list[str] | None = None, model: str | None = None,
  seed: int = 0, llm_backend=None) -> VerifyReport` (`D88`/`D93`): given
  `changed_ids`, MUST call `impact-analyzer` to compute the blast
  radius and check `provenance-checker` for a hit against each
  component's current `spec_bundle_hash`, same check `R-MERGE-024`
  used to make, reusing `provenance-checker`'s own function rather than
  re-deriving hit/miss logic against the raw `.provenance.json` files
  itself. Given no `changed_ids` (or an empty list), MUST check every
  component in `specs/components/` the same way — the whole-corpus
  scope.

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
  with enough detail (which component, which check failed) for a
  human or `provenance-tracker-ui` to act on, never just a bare
  boolean.

  **`impact-analyzer` MUST be loaded (imported/resolved) lazily, only
  at the point it is actually called, never eagerly at the top of
  `check_readiness` or in any setup step that runs regardless of
  scope** (`D98`): given no `changed_ids`, `impact-analyzer`'s own
  module is never loaded at all, not merely "called conditionally" —
  a real candidate loaded it unconditionally twice in a row despite
  this already being implied by *when* it is called, confirming that
  distinguishing "loaded" from "called" needs to be stated directly,
  not left to be inferred. `provenance-checker` is the one dependency
  genuinely needed by every scope and MAY be loaded unconditionally.

