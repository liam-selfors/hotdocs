# AC-GATE-003a

Covers: R-GATE-003
Kind: generated-test

```gherkin
Given a provenance miss and a faked run_attempts returning passed true
  with attempts [{"number": 1, "outcome": "verification_failed"},
  {"number": 2, "outcome": "passed"}], a generation result with one
  file, and a verification report with overall "pass"
When run_component_gates is called
Then run_attempts was called exactly once, blocked is false,
  block_reason is null, attempts is that two-entry list, and
  verification.overall is "pass"
```
