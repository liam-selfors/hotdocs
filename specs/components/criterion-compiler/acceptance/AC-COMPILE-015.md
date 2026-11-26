# AC-COMPILE-015

Covers: R-COMPILE-014
Kind: generated-test

```gherkin
Given a fresh directory holding a copy of the module under test's own
  source (its file, or its whole package directory), and
  criterion_compiler removed from sys.modules
When it is imported with that directory as the only addition to
  sys.path
Then the import succeeds, the module's __file__ lies in that directory,
  and it exposes compile and compile_criterion
```
