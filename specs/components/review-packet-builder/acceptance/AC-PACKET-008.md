# AC-PACKET-008

Covers: R-PACKET-008
Kind: compiled

```gherkin
Given a component whose spec_bundle_words is within 5% of D2's hard-fail
  threshold
When build_review_packet runs
Then residual_risk includes that finding
```
