# R-LOOP-004

**R-LOOP-004** — The loop MUST stop at the first `passed` attempt, with
  `passed` true and `stop_reason` `passed`, or after `max_attempts`
  attempts, with `stop_reason` `max_attempts`. On a pass in single mode
  it MUST call `generator`'s `commit_cache` with that attempt's result,
  the very object `generate` returned; in agentic mode, and on any
  failure, it never does. A `surface_failed` or `verification_failed`
  attempt MUST be followed by another while fewer than `max_attempts`
  have run, even when it added no feedback ids — except that a
  `verification_failed` attempt whose report has any criterion with
  `failure_origin` `"environment"`, or a `generation_failed` attempt
  whose category is `environment`, ends the loop at once with
  `stop_reason` `environment` (`D343`).
