# AC-LINT-016

Covers: R-LINT-016
Kind: compiled

```gherkin
Given a requirements/R-FOO-001.md file that carries a YAML frontmatter
  block (e.g. an id/title/status header)
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-016
```
