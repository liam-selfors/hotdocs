# AC-LINT-007

Covers: R-LINT-007
Kind: generated-test

```gherkin
Given a Behavior section containing a requirement bullet with no RFC 2119
  keyword in its text
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-007
```
