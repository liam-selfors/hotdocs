# AC-LINT-006

Covers: R-LINT-006
Kind: generated-test

```gherkin
Given a component component.md with sealed: false (or absent) and zero realizes
  entries
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-006
```
