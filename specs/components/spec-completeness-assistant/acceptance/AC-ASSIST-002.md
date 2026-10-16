# AC-ASSIST-002

Covers: R-ASSIST-002
Kind: compiled

```gherkin
Given a draft change to one spec whose dependents impact-analyzer resolves
  to two components
When assist runs
Then predicted_blast_radius lists exactly those two components
```
