# AC-XMODEL-007

Covers: R-XMODEL-007
Kind: compiled

```gherkin
Given fallback_standby_build enabled and cross_model_divergence_check
  disabled
When cross-check runs in standby-only mode
Then a verified second candidate is produced, diverged is null, and no
  output comparison is performed
```
