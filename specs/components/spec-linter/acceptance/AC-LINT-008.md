# AC-LINT-008

Covers: R-LINT-008
Kind: generated-test

```gherkin
Given a requirement R-FOO-001 with zero acceptance criteria whose Covers: tag
  names it
When hotdocs lint runs against the component
Then the report contains a fail-severity finding for rule R-LINT-008 naming
  R-FOO-001
```
