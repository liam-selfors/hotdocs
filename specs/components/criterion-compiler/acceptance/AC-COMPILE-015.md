# AC-COMPILE-015

Covers: R-COMPILE-014
Kind: generated-test

```gherkin
Given a fresh repo_root, the module under test's own source copied into
  repo_root/pipeline/criterion-compiler/ (its file, or its whole package
  directory), and criterion_compiler removed from sys.modules
When a caller resolves it via the documented algorithm (plain import
  first, then pipeline/criterion-compiler, then gen/criterion-compiler)
  with repo_root/pipeline/criterion-compiler as the location found
Then the import succeeds, the module's __file__ lies under
  repo_root/pipeline/criterion-compiler, and it exposes compile and
  compile_criterion
```
