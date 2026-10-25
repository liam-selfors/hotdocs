# AC-ASSEMBLE-010

Covers: R-ASSEMBLE-010
Kind: compiled

```gherkin
Given a component that depends_on comp-bar, whose Purpose section reads
  "Caches results." and whose Rationale section cites D13
When assemble runs for the dependent component
Then dependency_context["comp-bar"] is exactly "Caches results." — with
  no mention of D13 or any other Rationale content anywhere in the
  assembled bundle
```
