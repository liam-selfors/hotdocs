# R-TRACK-008

**R-TRACK-008** — MUST expose `last_requirement_failures(component_id,
  repo_root) -> list[str]`: the failing `R-id`s from the most recent
  `AttemptRecord` (written via this component's own
  `write_attempt_record`, called by `component-gate-runner`,
  `R-GATE-008`/`R-TRACK-007`) for that component whose `verification` is
  non-null, or an empty list if no such record exists. Pure read,
  read-only against `.hotdocs/attempts/` — this component only reads
  what it already wrote there itself. Exists solely so a human — or the
  CLI convenience built on it (`interface/cli.md`), or
  `provenance-tracker-ui`'s own display (`D88`) — has a one-step way to
  see what to pass as `hotdocs generate`'s own `--retry-feedback`
  (`D86`/`D93`), without removing the decision to actually pass it
  from their hands.
