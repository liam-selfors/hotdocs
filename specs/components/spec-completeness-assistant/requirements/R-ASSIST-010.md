# R-ASSIST-010

**R-ASSIST-010** — With a `model` configured, `assist` MUST make exactly
  two `llm-endpoint` `complete` calls, completeness first, then
  redundancy, and parse each response's `text` as JSON of exactly this
  shape:

  ```json
  {"completeness_score": 0.9, "completeness_rationale": "..."}
  {"redundancy_flags": [{"new_requirement": "R-FOO-005", "overlaps_with": "R-BAR-002", "rationale": "..."}]}
  ```

  A response wrapped in a Markdown code fence is unwrapped first. A
  `completeness_score` outside 0.0–1.0 is clamped to that range; a
  completeness response missing either field, with a score that is not
  a number (a boolean is not), or with an empty
  `completeness_rationale`, does not parse as that shape. A
  redundancy entry missing any of its three fields, or with an empty
  one, is dropped (`R-ASSIST-005`). If a call returns a
  `model_call_error`, or its text does not parse as that shape, that
  call's own fields stay `null`/`[]` — never guessed — and `assist`
  still returns normally; the other call's result is unaffected.

  These are the deterministic mechanics around the model call,
  testable with a faked `llm-endpoint`; whether the judgment itself is
  good is `AC-ASSIST-004`/`005`'s concern (`D160`).
