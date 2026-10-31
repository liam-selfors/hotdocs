# AC-PACKET-008

Covers: R-PACKET-008
Kind: generated-test

```gherkin
Given a component whose verification_report has overall "pass" but
  mutation_score below 1.0
When build_review_packet runs
Then residual_risk includes that finding
```
