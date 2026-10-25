# AC-GEN-012

Covers: R-GEN-011
Kind: generated-test

```gherkin
Given a mock model configured to hang (never respond) and the SDK's own
  default timeout
When generate is called
Then the call eventually completes with model_call_error set (not an
  unbounded hang), and the mock model records exactly one call attempt —
  no internal retry occurred
```
