# AC-LINT-018b

Covers: R-LINT-018
Kind: generated-test

```gherkin
Given a component's depends_on_guarantees lists G-DOES-NOT-EXIST
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-018
```
