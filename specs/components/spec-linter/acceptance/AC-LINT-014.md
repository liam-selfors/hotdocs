# AC-LINT-014

Covers: R-LINT-014
Kind: generated-test

```gherkin
Given two files under specs/ that both declare themselves a corpus glossary,
  with no architecture/ spec recording a bounded-context split decision
When hotdocs lint runs against the corpus
Then the report contains a fail-severity finding for rule R-LINT-014
```
