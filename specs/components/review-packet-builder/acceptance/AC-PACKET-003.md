# AC-PACKET-003

Covers: R-PACKET-003
Kind: generated-test

```gherkin
Given provenance-tracker's check_readiness result has two components
  in its components map
When build_review_packet runs
Then regenerated_components lists exactly those two component ids
```
