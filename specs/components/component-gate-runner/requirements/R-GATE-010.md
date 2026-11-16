# R-GATE-010

**R-GATE-010** — The `judge` closure, given a `CriterionBundle`, MUST
  make exactly one `llm-endpoint` `complete` call whose prompt contains
  the bundle's `criterion_text`, `requirement_text`, and `interface`,
  and the full text of every file under `gen/<slug>/` (skipping
  `__pycache__`), and asks for JSON
  `{"result": "pass" | "fail", "rationale": "..."}`. A response
  wrapped in a Markdown code fence is unwrapped first. It returns that
  `{result, rationale}`. A `model_call_error`, unparseable text, or a
  `result` other than `"pass"`/`"fail"` returns `{"result": "fail",
  "rationale": "judge unavailable: <reason>"}` — never a pass, and
  never raised (`D166`).
