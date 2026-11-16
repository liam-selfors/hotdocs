# R-AUTHOR-023

**R-AUTHOR-023** — The prompt MUST instruct that a test asserting a
  wall-clock "own write time" field falls within a `[before, after]`
  window MUST truncate `before`/`after` to the same precision the
  field's own documented format carries (e.g. whole seconds for a
  `%Y-%m-%dT%H:%M:%SZ` example with no fractional digits) — never
  compare a truncated-on-write timestamp against microsecond-precision
  bounds directly.
