# AC-MUT-004

Covers: R-MUT-004
Kind: generated-test

```gherkin
Given qux.py whose qux() returns 2 * 2, and two tests asserting
  qux.qux() == 4, the second also asserting
  (Path.cwd() / "specs").is_dir()
When score is called with both
Then faulty_tests is [the second], mutation_error is None and
  mutation_score is 1.0

Given only that second test
When score is called with it
Then faulty_tests is [it], and mutation_score and mutation_error are
  None
```
