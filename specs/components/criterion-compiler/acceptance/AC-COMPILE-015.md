# AC-COMPILE-015

Covers: R-COMPILE-014
Kind: generated-test

```gherkin
Given a repo_root whose pipeline/criterion-compiler/ holds this real
  component, and criterion_compiler not already present in sys.modules
When a caller resolves it via the documented algorithm (plain import
  first, then pipeline/criterion-compiler, then gen/criterion-compiler)
Then the import succeeds and the resulting module exposes both compile
  and compile_criterion
```
