# AC-UI-002

Covers: R-UI-002
Kind: compiled

```gherkin
Given two TrackingRecords, the first with comp-foo as a model_call_error
  and the second with comp-foo passing verification
When the page renders comp-foo's history
Then both attempts are shown in chronological order with their actual
  recorded outcomes, not a recomputed or collapsed single status
```
