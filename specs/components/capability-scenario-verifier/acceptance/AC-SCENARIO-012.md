# AC-SCENARIO-012

Covers: R-SCENARIO-004
Kind: generated-test

```gherkin
Given a fresh run whose only scenario fails
When run_capability_gates completes
Then the record exists with that failing report, hit is false, and the
  returned report's overall is "fail"

Given that record and unchanged code
When check_capability_provenance is called, and then run_capability_gates
  with model None
Then both report hit true with overall "fail", and no fake module was
  called — a recorded failure is not hidden and not re-run
```
