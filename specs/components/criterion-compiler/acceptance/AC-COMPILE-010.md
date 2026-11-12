# AC-COMPILE-010

Covers: R-COMPILE-010
Kind: generated-test

```gherkin
Given a component compiled once, reporting the module's GATE_VERSION
When the module's GATE_VERSION attribute is replaced by
  "criterion-compiler@1.1.0" and the same component is compiled again
Then the second CompileReport.gate_version is
  "criterion-compiler@1.1.0", differing from the first
```
