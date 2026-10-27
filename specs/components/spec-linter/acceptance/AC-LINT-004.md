# AC-LINT-004

Covers: R-LINT-004
Kind: generated-test

```gherkin
Given two component specs whose depends_on entries form a cycle (A depends_on
  B, B depends_on A)
When hotdocs lint runs against the corpus
Then the report contains a fail-severity finding for rule R-LINT-004 naming
  both components
```
