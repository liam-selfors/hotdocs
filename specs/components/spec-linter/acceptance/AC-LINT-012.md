# AC-LINT-012

Covers: R-LINT-012
Kind: generated-test

```gherkin
Given a component whose generated-code LOC estimate exceeds 1500
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-012 citing
  the "Generated code per component" dimension
```
