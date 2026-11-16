# AC-COMPILE-001

Covers: R-COMPILE-001
Kind: generated-test

```gherkin
Given acceptance/ content containing a step that does not match any
  recognized template in the step grammar
When compile-criteria runs against it
Then the CompileReport marks that criterion status: error, naming the exact
  file, line, and the unmatched step text — not a silent skip
```
