# R-SCENARIO-008

**R-SCENARIO-008** — `run_capability_gates` MUST build its own `judge`
  callable. It is the contract `component-gate-runner`'s `R-GATE-010`
  states, stated here too because a bundle never carries another
  component's requirements. Given a scenario bundle, it makes exactly one
  `llm-endpoint` `complete(prompt, model, backend=llm_backend)` call.
  The prompt contains the scenario's Gherkin and `covers`, and the full
  text of every file under the code directory of each realizing
  component (skipping `__pycache__`), and asks for JSON
  `{"result": "pass" | "fail", "rationale": "..."}`.

  The JSON parsed is the reply's whole text, stripped; or, when the
  reply has a line starting with three backticks, the lines between
  the first such line and the next one, so prose before or after a
  fenced block is ignored (`D338`). The callable returns the parsed `{result, rationale}`. A
  `model_call_error`, unparseable text, or a `result` other than
  `"pass"` or `"fail"` returns `{"result": "fail", "rationale": "judge
  unavailable: <reason>"}` — never a pass, and never raised.
