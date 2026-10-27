# AC-GRAPH-003

Covers: R-GRAPH-003
Kind: generated-test

```gherkin
Given a component with a known VerificationReport and provenance manifest
When build_corpus_graph runs
Then that component's node carries both, plus its size status and sealed
  status
```
