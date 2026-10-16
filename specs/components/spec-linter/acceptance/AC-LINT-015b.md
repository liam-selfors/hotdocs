# AC-LINT-015b

Covers: R-LINT-015
Kind: llm-judge

```gherkin
Given no model is configured for the linter at all
When hotdocs lint runs against a component with a Definitions-section entry
  that would otherwise need an R-LINT-015 judgment
Then R-LINT-015 is skipped with a visible, non-silent notice in the report —
  neither treated as passing nor causing a crash
```
