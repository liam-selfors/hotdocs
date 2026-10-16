# AC-LINT-013

Covers: R-LINT-013
Kind: compiled

```gherkin
Given a specs/vars/ declaration with sensitivity: secret and a default field
  present
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-013
```
