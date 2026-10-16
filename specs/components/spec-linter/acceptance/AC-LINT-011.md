# AC-LINT-011

Covers: R-LINT-011
Kind: compiled

```gherkin
Given a component's Definitions section whose entry for a glossary term is a
  near-verbatim copy (token-overlap ratio >= 0.8) of that term's definition in
  specs/glossary.md
When hotdocs lint runs against the component
Then the report contains a fail-severity finding for rule R-LINT-011
```
