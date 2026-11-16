# AC-VERIFY-015

Covers: R-VERIFY-006
Kind: generated-test

```gherkin
Given a component with two generated-test-kind criteria, each testing
  a different one of two functions in the same module, each test
  covering its own function fully
When verify runs
Then the reported mutation_score reflects the union of both tests
  killing mutants (high), never either test's own isolated score
  against the whole module (which would be far lower)
```
