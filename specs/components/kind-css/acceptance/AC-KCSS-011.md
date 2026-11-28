# AC-KCSS-011

Covers: R-KCSS-009
Kind: generated-test

```gherkin
Given the two sections Generator guidance and Test author guidance of
  specs/architecture/asset-kind-css.md, each copied into the test as a
  string literal exactly as R-KCSS-009 extracts it
When guidance() is called twice
Then each result equals {"generator": <the first literal>,
  "test_author": <the second literal>}, and changing one result's
  "generator" value does not change the other result
```
