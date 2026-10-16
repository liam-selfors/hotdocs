# AC-VERIFY-006

Covers: R-VERIFY-006
Kind: compiled

```gherkin
Given a component with a generated-test-kind criterion whose mutation score
  is below the published bar
When verify runs
Then the overall verdict is fail, citing the mutation-score shortfall
```
