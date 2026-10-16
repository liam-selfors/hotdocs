# AC-LINT-002

Covers: R-LINT-002
Kind: compiled

```gherkin
Given a component component.md with status: ratified and a non-empty
  "Open questions" section
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-002
```
