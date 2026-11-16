# AC-ASSIST-005

Covers: R-ASSIST-005
Kind: llm-judge

```gherkin
Given a draft change that restates, in different words, a requirement
  already present elsewhere in the corpus
When assist runs with a model configured
Then redundancy_flags contains one entry whose new_requirement is the
  draft change's own R-id, whose overlaps_with is the pre-existing R-id
  it restates, and whose rationale is non-empty
```
