# AC-PACKET-008

Covers: R-PACKET-008
Kind: generated-test

```gherkin
Given a component whose component_doc_words is within 5% of the hard-fail
  threshold
When build_review_packet runs
Then residual_risk includes that finding
```
