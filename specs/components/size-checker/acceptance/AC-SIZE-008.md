# AC-SIZE-008

Covers: R-SIZE-001
Kind: generated-test

```gherkin
Given a component comp-big with 21 requirement files, one acceptance
  file covering one of them, an interface/library.md of 8100 words of
  prose, and gen/big/big.py holding 801 code lines, 40 lines starting
  "#" (after leading spaces) and 40 blank lines
When check(repo_root) runs
Then comp-big gets warn R-SIZE-001 findings whose messages name
  requirement_count with 21, generated_code_loc with 801,
  generator_words with a value above 8000 and criterion_words_max with
  a value above 6000, and no fail R-SIZE-001 finding
```
