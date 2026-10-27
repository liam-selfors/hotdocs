# AC-GATE-003c

Covers: R-GATE-003
Kind: generated-test

```gherkin
Given a mock generator that returns model_call_error on its one call
When run_component_gates is called
Then generator is called exactly once — never a second time — and the
  result is blocked with a reason distinguishing "no candidate was ever
  produced" from a verification failure
```
