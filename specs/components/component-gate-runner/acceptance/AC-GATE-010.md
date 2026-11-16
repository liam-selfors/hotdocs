# AC-GATE-010

Covers: R-GATE-010
Kind: generated-test

```gherkin
Given gen/foo/foo.py containing "MARKER_SOURCE", a faked verify that
  calls the judge it receives with {"criterion_text": "MARKER_CRIT",
  "requirement_text": "MARKER_REQ", "interface": "MARKER_IFACE"} and
  records the outcome, and a faked llm-endpoint whose complete returns
  text holding {"result": "pass", "rationale": "ok"} inside a
  Markdown code fence
When run_component_gates is called on a provenance miss
Then complete was called once with a prompt containing all four
  markers, and the recorded judge outcome's result is "pass" with
  rationale "ok"

Given complete instead returns a model_call_error, or the text
  "not json", or {"result": "maybe"}
When the judge is called
Then the outcome's result is "fail" and its rationale begins
  "judge unavailable"
```
