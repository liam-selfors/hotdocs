# AC-LINT-005

Covers: R-LINT-005
Kind: compiled

```gherkin
Given a component component.md with sealed: true and no source_path field
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-005
```
