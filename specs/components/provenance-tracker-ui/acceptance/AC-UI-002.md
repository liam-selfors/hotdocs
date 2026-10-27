# AC-UI-002

Covers: R-UI-002
Kind: generated-test

```gherkin
Given a VerifyReport where comp-foo is a passing hit and comp-bar is a
  miss, and a CapabilityProvenanceCheckResult where P-ZERO-EDIT is a
  failing hit
When the page renders this scope
Then comp-foo's node is styled as passing, comp-bar's node is styled as
  missing, and P-ZERO-EDIT's node is styled as failing — each a direct
  render of the report's own fields, not a recomputed or collapsed
  status
```
