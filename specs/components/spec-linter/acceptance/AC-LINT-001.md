# AC-LINT-001

Covers: R-LINT-001
Kind: generated-test

```gherkin
Given a component component.md with no `owners` field in its frontmatter
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-001
```
