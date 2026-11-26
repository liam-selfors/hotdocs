# R-TRACK-007

**R-TRACK-007** — MUST expose `write_attempt_record`, writing one
  `AttemptRecord` per component per `hotdocs generate` attempt to
  `.hotdocs/attempts/<component_id>/` — the full `GenerationResult` and,
  if generation reached it, the full `VerificationReport`, taken as
  direct parameters from `component-gate-runner`.

  Written for both outcomes, success and failure (`D19`).

  **The returned `AttemptRecord`'s own `generation`/`verification`
  fields MUST be the same JSON-equivalent plain form written to disk**
  (`D100`, `AttemptRecord.md`) — never the original
  `GenerationResult`/`VerificationReport` object echoed back by
  reference. Each input may be a dict, a dataclass, or any object
  with attributes, and is converted to plain JSON values before writing
  exactly as `specs/architecture/json-values.md` gives, so a `set` or
  any other value inside a failing criterion's `failure_detail` never
  stops the write (`D318`).
