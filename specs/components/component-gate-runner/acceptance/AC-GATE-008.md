# AC-GATE-008

Covers: R-GATE-008
Kind: generated-test

```gherkin
Given a provenance miss whose key has spec_bundle_hash "sha256:k", one
  generated file, and verify returning overall "fail"
When run_component_gates is called
Then write_attempt_record was called exactly once, after both scans,
  with "comp-foo", the generator's result, verify's report, and
  "sha256:k"

Given a faked generator returning a model_call_error
When run_component_gates is called
Then write_attempt_record received None as its verification report

Given a faked write_attempt_record that raises RuntimeError
When run_component_gates is called with a passing candidate
Then it returns normally with blocked false
```
