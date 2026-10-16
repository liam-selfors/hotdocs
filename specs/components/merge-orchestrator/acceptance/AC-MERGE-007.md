# AC-MERGE-007

Covers: R-MERGE-007
Kind: compiled

```gherkin
Given cross_model_divergence_check disabled and fallback_standby_build
  disabled for a component
When run_merge is called
Then cross-model-divergence-checker is never invoked for that component
```
