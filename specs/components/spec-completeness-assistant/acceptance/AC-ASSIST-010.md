# AC-ASSIST-010

Covers: R-ASSIST-010
Kind: generated-test

```gherkin
Given a repo_root with faked spec-linter (no findings), impact-analyzer
  (blast radius comp-foo), spec-bundle-assembler, and generator
  modules, and a faked llm-endpoint whose complete returns, in call
  order, a completeness response {"completeness_score": 0.7,
  "completeness_rationale": "AC missing"} wrapped in a Markdown code
  fence (a line of three backticks, optionally tagged json, before it
  and a line of three backticks after it),
  then a redundancy response holding one complete entry and one entry
  with an empty rationale
When assist(changed_ids, repo_root, model="fake-model") runs
Then the faked llm-endpoint was called exactly twice,
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
