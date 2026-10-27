# R-TRACK-008

**R-TRACK-008** — MUST expose `last_requirement_failures(component_id,
  repo_root) -> list[str]`: the failing `R-id`s from the most recent
  `AttemptRecord` (`R-TRACK-007`) for that component whose
  `verification` is non-null, or an empty list if no such record
  exists. Pure read, read-only against `.hotdocs/attempts/` — this
  function MUST NOT be called by `component-gate-runner` itself
  (`hotdocs generate`'s own `--retry-feedback` is explicit that it is
  caller-supplied, never derived mid-attempt); it exists solely so a
  human — or the CLI convenience built on it (`interface/cli.md`), or
  `provenance-tracker-ui`'s own display (`D88`) — has a one-step way to
  see what to pass as `hotdocs generate`'s own `--retry-feedback`
  (`D86`), without removing the decision to actually pass it from
  their hands.
