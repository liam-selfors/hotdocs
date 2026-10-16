# AC-COMPILE-002

Covers: R-COMPILE-002
Kind: generated-test

```gherkin
Given an acceptance/ step that references a function name not declared in
  the paired component's interface/ contract
When compile-criteria runs
Then the CompileReport marks that criterion status: error, naming the
  unresolved reference
```
