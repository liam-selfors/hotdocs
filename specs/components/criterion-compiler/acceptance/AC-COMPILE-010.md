# AC-COMPILE-010

Covers: R-COMPILE-010
Kind: generated-test

```gherkin
Given two versions of the compiler where the step grammar has changed
  between them
When each version compiles the same component's acceptance/ and interface/
  content
Then CompileReport.gate_version differs between the two runs
```
