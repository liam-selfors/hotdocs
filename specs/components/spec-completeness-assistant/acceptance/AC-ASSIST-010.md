# AC-ASSIST-010

Covers: R-ASSIST-010
Kind: generated-test

```gherkin
Given a repo_root whose R-FOO-001 and R-BAR-001 read the same apart
  from their ids (so they are a candidate pair), stand-ins
  for all four dependencies, lint returning no findings, a blast radius
  of comp-foo, a glossary_judge stand-in returning a callable the test
  can identify, and an llm-endpoint stand-in whose complete returns, in
  call order, a completeness response {"completeness_score": 0.7,
  "completeness_rationale": "AC missing"} inside a code fence tagged
  json, then a redundancy response holding one complete entry, R-FOO-001
  overlapping R-BAR-001, and one entry for the same pair with an empty
  rationale
When assist(["R-FOO-001"], repo_root, model="fake-model") runs
Then the llm-endpoint stand-in was called exactly twice, lint received
  that callable as judge,
  completeness_score is 0.7, completeness_rationale is "AC missing",
  redundancy_flags holds only the complete entry, and degraded is false

Given the faked llm-endpoint instead returns a model_call_error for the
  completeness call and unparseable text for the redundancy call
When assist runs with model="fake-model"
Then it returns normally, completeness_score and completeness_rationale
  are null, and redundancy_flags is []

Given the completeness response is {"completeness_score": 0.6,
  "completeness_rationale": ""}
When assist runs with model="fake-model"
Then completeness_score and completeness_rationale are both null

Given the completeness response is {"completeness_rationale": "x"}, or
  {"completeness_score": true, "completeness_rationale": "x"}, or the
  empty string
When assist runs with model="fake-model"
Then completeness_score and completeness_rationale are both null

Given the completeness response's completeness_score is 1.7
When assist runs with model="fake-model"
Then completeness_score is 1.0
```
