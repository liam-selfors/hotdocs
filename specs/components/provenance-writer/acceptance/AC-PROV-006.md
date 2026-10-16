# AC-PROV-006

Covers: R-PROV-006
Kind: compiled

```gherkin
Given no CrossCheckResult was provided (the gate did not run)
When write_provenance runs
Then cross_model_check is the literal string "not-run", not absent from the
  manifest
```
