# AC-GATE-006

Covers: R-GATE-006
Kind: generated-test

```gherkin
Given generation, verification, and both scans have completed for a
  component
When run_component_gates is called
Then provenance-writer is invoked only after all of them have produced
  results
```
