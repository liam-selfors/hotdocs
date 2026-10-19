# AC-COMPILE-011

Covers: R-COMPILE-011
Kind: generated-test

```gherkin
Given a component with one valid kind: compiled criterion
When compile-criteria is invoked with --target=jest (an unimplemented
  target)
Then compilation fails with exit code 2, the error names "jest" as the
  unsupported target, and no output file is written under
  verification/<component>/compiled/

Given the same component
When compile-criteria is invoked with --target=pytest
Then compilation succeeds and produces the same bound facts (resolved
  fixture/function/assertion content) regardless of target — demonstrated
  by compiling twice with no change to acceptance/ or interface/ content
  and confirming byte-identical pytest output (R-COMPILE-003), the
  parse+bind phase having no observable dependency on --target
```
