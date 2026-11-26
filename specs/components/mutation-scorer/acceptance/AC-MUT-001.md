# AC-MUT-001

Covers: R-MUT-001
Kind: generated-test

```gherkin
Given gen/qux/qux.py defining qux() returning 2 * baz() with baz loaded
  from Path(__file__).resolve().parents[1] / "baz" / "baz.py", a
  gen/baz/baz.py whose baz() returns 2, and one test asserting
  qux.qux() == 4
When score("comp-qux", repo_root, [that test], environment) is called
Then mutation_error is None and mutation_score is 1.0, and
  gen/qux/qux.py is unchanged

Given a conftest.py beside the test that puts repo_root/gen/qux first
  on sys.path and imports qux, and one test failing on every mutant of
  qux's one function
When score is called
Then mutation_score is 1.0

Given no tests
When score("comp-qux", repo_root, [], environment) is called
Then mutation_score is None, mutation_error is None and mutants is 0
```
