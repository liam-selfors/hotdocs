# AC-VERIFY-015

Covers: R-VERIFY-006
Kind: generated-test

```gherkin
Given a component with two generated-test-kind criteria, each fully
  testing a different one of two functions in the same module
When verify runs
Then mutation_score is the union of both tests' kills (high), never
  either test's own score against the whole module
```
