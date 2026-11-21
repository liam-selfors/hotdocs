# R-ASSIST-010

**R-ASSIST-010** — With a `model` configured, `assist` MUST make one
  `llm-endpoint` `complete` call for completeness and then, only when
  `R-ASSIST-005` found a candidate pair, one for redundancy, and MUST
  pass `spec-reviewer`'s `glossary_judge(model, llm_backend)` to `lint`
  as `judge`. Two requirements whose texts differ only in their ids are
  always a candidate pair. It parses each response's `text` as JSON of
  the reply shape `interface/library.md` gives.

  A text that, stripped, opens with a line of three backticks
  (optionally tagged `json`) and closes with a line of three backticks
  is unwrapped to the lines between them first. A `completeness_score`
  outside 0.0–1.0 is clamped to that range; a completeness response
  missing either field, with a score that is not a number (a boolean is
  not), or with an empty `completeness_rationale`, does not parse. A
  redundancy entry missing any of its three fields, or with an empty
  one, is dropped, as is one whose pair was not a candidate; the rest
  are kept in reply order. If a call returns a `model_call_error`, or
  its text does not parse, that call's own fields stay `null`/`[]` —
  never guessed — and `assist` still returns normally, with `degraded`
  false; the other call's result is unaffected.
