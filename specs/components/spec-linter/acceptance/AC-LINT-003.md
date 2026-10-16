# AC-LINT-003

Covers: R-LINT-003
Kind: compiled

```gherkin
Given a component component.md whose depends_on lists an id with no
  corresponding spec file anywhere under specs/
When hotdocs lint runs
Then the report contains a fail-severity finding for rule R-LINT-003 naming
  the dangling id
```
