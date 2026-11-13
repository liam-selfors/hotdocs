# AC-VERIFY-005

Covers: R-VERIFY-005
Kind: generated-test

```gherkin
Given a component where every compiled and generated-test criterion passes,
  its tests kill every mutant (mutation_score 1.0), interface_drift is
  false, and the only llm-judge criterion is skipped
When verify runs
Then the overall verdict is pass — a skipped finding alone never causes fail
```
