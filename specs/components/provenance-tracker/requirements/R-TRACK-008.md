# R-TRACK-008

**R-TRACK-008** — MUST expose `last_requirement_failures(component_id,
  repo_root) -> list[str]`: the failing `R-id`s from the most recent
  `AttemptRecord` for that component whose `verification` is
  non-null, or an empty list if no such record exists. Pure read,
  read-only against `.hotdocs/attempts/`.

  **`verification.requirement_results` MUST be read as a flat `R-id ->
  "pass"|"fail"` string mapping** (`D95`, `AttemptRecord.md`). An
  `R-id` it marks `"fail"` is left out when every entry of
  `verification.criteria` that covers it and whose `result` is not
  `"pass"` has `failure_origin` `"test"` or `"environment"`: no test
  could be written or run for it, so it is no feedback for the next
  generation (`D319`, `D343`).
