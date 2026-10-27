# AC-ASSEMBLE-012

Covers: R-ASSEMBLE-001
Kind: generated-test

```gherkin
Given a component whose component.md has distinctive text under
  Rationale, Open questions, and Change log, alongside its Purpose
  and Scope sections
When assemble runs in cold mode for that component
Then the resulting SpecBundle's spec field contains the Purpose and
  Scope text but none of the Rationale, Open questions, or Change log
  text
```
