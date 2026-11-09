# AC-LINT-023

Covers: R-LINT-023
Kind: generated-test

```gherkin
Given one requirement file over 500 words and a second requirement file
  in the same component under 250 words, with the component's overall
  component_doc_words still under 4000
When the linter runs
Then the first file gets a fail-severity R-LINT-023 finding naming its
  own word count, the second file gets no R-LINT-023 finding, and
  R-LINT-012's component_doc_words check does not fire
```
