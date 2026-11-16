# AC-SCENARIO-011

Covers: R-SCENARIO-008
Kind: generated-test

```gherkin
Given gen/foo/foo.py containing "MARKER_SOURCE" realizing P-X, an
  llm-judge scenario CS-X-001 with gherkin containing "MARKER_GHERKIN",
  and a fake llm-endpoint whose complete records its arguments and
  returns text holding {"result": "pass", "rationale": "ok"} inside a
  Markdown code fence
When run_capability_gates("P-X", repo_root, "m", llm_backend=<sentinel>)
  is called
Then complete was called exactly once, with model "m", the sentinel
  backend, and a prompt containing both markers, and the scenario's
  result is "pass" with rationale "ok"

Given complete instead returns a model_call_error, or the text "not
  json", or {"result": "maybe"}
When the same call is made
Then the scenario's result is "fail" and its rationale begins "judge
  unavailable"
```
