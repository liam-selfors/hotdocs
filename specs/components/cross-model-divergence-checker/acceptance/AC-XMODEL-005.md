# AC-XMODEL-005

Covers: R-XMODEL-005
Kind: compiled

```gherkin
Given two candidates that both pass verification but produce different
  outputs for the same input, in divergence mode
When cross-check runs
Then diverged is true, divergence_detail names the specific criterion
  involved, and the result is merge-blocking (exit code 1)
```
