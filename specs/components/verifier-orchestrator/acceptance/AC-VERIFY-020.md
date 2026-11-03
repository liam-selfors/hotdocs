# AC-VERIFY-020

Covers: R-VERIFY-006
Kind: generated-test

```gherkin
Given a component whose only module defines g(a, b) containing one
  comparison "a < b", h(a, b) returning "a // b", and m(k, d) returning
  "k in d", plus a do_the_thing(x) with no operators, and one cached
  generated-test test that kills only the mutant of "a < b"
When verify runs
Then mutation_score is exactly 1/3: three sites, one killed
```
