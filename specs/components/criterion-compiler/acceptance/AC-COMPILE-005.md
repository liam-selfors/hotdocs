# AC-COMPILE-005

Covers: R-COMPILE-005
Kind: generated-test

```gherkin
Given an acceptance/ directory containing one Kind: compiled criterion and
  one Kind: llm-judge criterion
When compile-criteria runs
Then the compiled criterion produces an emitted test file and the llm-judge
  criterion appears in CompileReport.summary.skipped_non_compiled_kind, not as
  an error
```
