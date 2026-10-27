# R-TRACK-009

**R-TRACK-009** — MUST expose `check_readiness(repo_root: Path,
  changed_ids: list[str] | None = None) -> VerifyReport` (`D88`): given
  `changed_ids`, MUST call `impact-analyzer` to compute the blast
  radius and check `provenance-checker` for a hit against each
  component's current `spec_bundle_hash`, same check `R-MERGE-024`
  used to make, reusing `provenance-checker`'s own function rather than
  re-deriving hit/miss logic against the raw `.provenance.json` files
  itself. Given no `changed_ids` (or an empty list), MUST check every
  component in `specs/components/` the same way — the whole-corpus
  scope.

  A component whose check is a miss or whose hit carries a failing
  `verification_report`/blocking scan result is reported as not ready,
  with enough detail (which component, which check failed) for a
  human or `provenance-tracker-ui` to act on, never just a bare
  boolean.
