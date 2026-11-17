# AC-VERIFY-025

Covers: R-VERIFY-014
Kind: generated-test

```gherkin
Given an unsealed comp-foo whose gen/foo/foo.py defines foo() returning
  2 * bar() with bar loaded from
  Path(__file__).resolve().parents[1] / "bar" / "bar.py", a
  gen/bar/bar.py whose bar() returns 2, and one cached generated test
  asserting foo.foo() == 4
When verify runs
Then that criterion is pass, mutation_error is None and mutation_score
  is 1.0

Given an unsealed comp-foo whose gen/foo/foo.py defines foo() returning
  2 * 2, and one cached generated test asserting foo.foo() == 4 and
  (Path.cwd() / "specs").is_dir()
When verify runs
Then that criterion is pass, mutation_score is None, overall is "fail"
  and mutation_error is
  "mutation baseline failed in the sandbox: pytest exited 1"
```
