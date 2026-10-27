# AC-LINT-017

Covers: R-LINT-017
Kind: generated-test

```gherkin
Given a file under interface/guarantees/ named G-FOO-001.md whose own
  heading says G-FOO-002
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-017
```
