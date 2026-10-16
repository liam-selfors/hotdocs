# AC-VERIFY-007

Covers: R-VERIFY-007
Kind: compiled

```gherkin
Given any component
When verify runs
Then exactly one VerificationReport is produced containing per-criterion
  results, mutation_score, interface_drift, and overall
```
