# AC-LINT-033

Covers: R-LINT-033
Kind: generated-test

```gherkin
Given a corpus whose only problems are a component.md citing a
  decision number that has no decision file, and a Purpose section of
  160 words
When lint(None, repo_root) runs
Then the report holds a fail-severity R-CITE-001 finding for the
  citation and a fail-severity R-SIZE-004 finding for the Purpose, each
  as a Finding with that component.md as its file, and hard_failures is
  2

Given the same corpus
When load_corpus is read from the module under test
Then it returns a Corpus with that component under components
```
