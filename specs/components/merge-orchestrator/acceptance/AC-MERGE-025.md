# AC-MERGE-025

Covers: R-MERGE-023
Kind: generated-test

```gherkin
Given a blast radius containing comp-bar and comp-foo, where comp-foo
  depends_on comp-bar
When run_merge sequences their component-gate-runner calls
Then comp-bar's component-gate-runner call completes before comp-foo's
  begins
```
