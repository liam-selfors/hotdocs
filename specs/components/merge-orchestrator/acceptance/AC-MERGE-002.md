# AC-MERGE-002

Covers: R-MERGE-002
Kind: generated-test

```gherkin
Given a lint-clean corpus and one changed spec id
When run_merge is called
Then impact-analyzer is invoked with that id and its result determines
  which components proceed
```
