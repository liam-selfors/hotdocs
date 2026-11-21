# AC-GATE-008

Covers: R-GATE-008
Kind: generated-test

```gherkin
Given a provenance miss whose key has spec_bundle_hash "sha256:k" and a
  faked run_attempts that calls on_attempt twice: first with a
  generation result G1 and report None, then with G2 and report R2
When run_component_gates is called
Then write_attempt_record was called exactly twice, first with
  "comp-foo", G1, None and "sha256:k", then with "comp-foo", G2, R2
  and "sha256:k"

Given a faked write_attempt_record that raises RuntimeError and a
  passing loop
When run_component_gates is called
Then it returns normally with blocked false
```
