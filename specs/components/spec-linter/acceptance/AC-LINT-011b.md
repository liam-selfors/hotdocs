# AC-LINT-011b

Covers: R-LINT-011
Kind: generated-test

```gherkin
Given a component's Definitions section whose entry for a glossary term adds
  genuinely new, component-specific nuance with low textual overlap against
  the glossary's definition
When hotdocs lint runs against the component
Then the report contains no R-LINT-011 finding — this is a permitted delta,
  not a redefinition
```
