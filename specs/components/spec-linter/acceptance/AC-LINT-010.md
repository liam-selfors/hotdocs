# AC-LINT-010

Covers: R-LINT-010
Kind: compiled

```gherkin
Given an acceptance criterion block missing a Kind: tag
When hotdocs lint runs against the component
Then the report contains a fail-severity finding for rule R-LINT-010
```
