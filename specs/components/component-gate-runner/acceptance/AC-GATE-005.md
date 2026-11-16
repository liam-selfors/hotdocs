# AC-GATE-005

Covers: R-GATE-005
Kind: generated-test

```gherkin
Given a provenance miss and a faked generator returning a
  model_call_error
When run_component_gates is called
Then license-scanner's scan was called with "comp-foo" and repo_root,
  and secret-scanner's scan with repo_root, and the result carries
  both scan results

Given a short-circuiting provenance hit
When run_component_gates is called
Then neither scanner was called
```
