# AC-SIZE-003

Covers: R-SIZE-003
Kind: generated-test

```gherkin
Given one requirement file over 500 words and a second requirement file
  in the same component under 250 words, with the component's overall
  component_doc_words still under 4000
When check(repo_root) runs
Then the first file gets a fail-severity R-SIZE-003 finding naming its
  own word count, the second file gets no R-SIZE-003 finding, and
  R-SIZE-001's component_doc_words check does not fire
```
