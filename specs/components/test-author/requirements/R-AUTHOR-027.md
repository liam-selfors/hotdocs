# R-AUTHOR-027

**R-AUTHOR-027** — For a rejected test, `author_test` MUST make up to two
  repair calls. Each repair prompt is the original prompt followed by the
  rejected test's full source and one line per `error` finding,
  `<kind> (line <line>): <message>`, asking for the complete corrected
  file in the same markers with a fresh nonce. A reply is extracted and
  probed as the first was; the first test whose probe is `ok` is the
  result. When no test passes after the second repair, or a call returns
  a `model_call_error`, the result has `model_call_error` with category
  `test_probe_failed` (or that call's own error), a null `file`, and
  nothing is cached or written. `repair_attempts` counts the repair calls
  made and `probe_findings` holds the findings, as dicts, of the last
  probe run.
