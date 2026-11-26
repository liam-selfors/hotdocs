# AC-MUT-002

Covers: R-MUT-002
Kind: generated-test

```gherkin
Given qux.py defining g(a, b) containing one comparison "a < b", h(a, b)
  returning "a // b", m(k, d) returning "k in d" and do_the_thing(x)
  with no operators, and one test that kills only the mutant of "a < b"
When score is called
Then mutants is 3, killed is 1 and mutation_score is exactly 1/3

Given qux.py defining f1 and f2, each with one comparison, and two
  tests, each fully testing one of them
When score is called with both
Then mutation_score is 1.0

Given qux.py defining only qux() returning None, the fake kind
  declared, and one test asserting asset_runner("data/table.txt")("a",
  []) == 1
When score is called
Then mutation_score is 0.5; with the test also asserting
  asset_runner("data/table.txt")("b", []) == 2, it is 1.0
```
