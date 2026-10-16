# AC-PACKET-001

Covers: R-PACKET-001
Kind: compiled

```gherkin
Given a PR changing one component's spec.md
When build_review_packet runs
Then spec_diff contains the actual diff text for that file
```
