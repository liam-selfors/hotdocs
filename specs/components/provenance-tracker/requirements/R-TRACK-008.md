# R-TRACK-008

**R-TRACK-008** — MUST expose `last_requirement_failures(component_id,
  repo_root) -> list[str]`: the failing `R-id`s from the most recent
  `AttemptRecord` (written directly by `component-gate-runner`,
  `R-GATE-008`, `D92`) for that component whose `verification` is
  non-null, or an empty list if no such record exists. Pure read,
  read-only against `.hotdocs/attempts/` — this component never writes
  to that directory itself, only reads what `component-gate-runner`
  already wrote there. Exists solely so a human — or the CLI
  convenience built on it (`interface/cli.md`), or
  `provenance-tracker-ui`'s own display (`D88`) — has a one-step way to
  see what to pass as `hotdocs build`'s own `--retry-feedback`
  (`D86`/`D92`), without removing the decision to actually pass it
  from their hands.
