# R-REVIEW-004

**R-REVIEW-004** — With a `model`, `check` MUST make one `complete` call
  per criterion whose prompt holds that criterion's bundle fields and
  nothing from any other criterion, and asks the model, as that test's
  author, to reply with one JSON object:

  ```
  {"writable": <bool>,
   "gaps": [{"kind": "guess" | "unstated_behavior", "missing": "<text>",
             "proposed_text": "<text>", "target_file": "<path>"}]}
  ```

  The reply's JSON is the text from its first `{` to its last `}`. A
  parsed object sets `writable[<criterion_id>]` and adds each gap, with
  `criterion_id` set, to `gaps`; a gap whose `kind` is neither allowed
  value is dropped. A reply that does not parse, lacks a bool `writable`,
  or carries a `model_call_error` sets `writable[<criterion_id>]` to
  `None` and adds one finding of kind `model_unparseable` whose `token` is
  `""` and whose `message` is the error, or `reply was not the JSON
  object asked for`. Without a `model`, every `writable` value is `None`,
  `gaps` is empty, no `complete` call is made and `degraded` is `true`.
