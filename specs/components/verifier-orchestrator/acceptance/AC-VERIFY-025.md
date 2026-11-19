# AC-VERIFY-025

Covers: R-VERIFY-014
Kind: generated-test

```gherkin
Given an unsealed comp-qux whose gen/qux/qux.py defines qux() returning
  2 * baz() with baz loaded from
  Path(__file__).resolve().parents[1] / "baz" / "baz.py", a
  gen/baz/baz.py whose baz() returns 2, and one cached generated test
  asserting qux.qux() == 4
When verify runs
Then that criterion is pass, mutation_error is None and mutation_score
  is 1.0

```
