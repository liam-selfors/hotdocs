# AC-MERGE-025

Covers: R-MERGE-023
Kind: generated-test

```gherkin
Given a blast radius containing comp-bar and comp-foo, where comp-foo
  depends_on comp-bar
When run_merge sequences their generation calls
Then comp-bar's generator call completes before comp-foo's begins
```
