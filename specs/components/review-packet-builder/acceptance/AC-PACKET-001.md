# AC-PACKET-001

Covers: R-PACKET-001
Kind: generated-test

```gherkin
Given a PR changing one component's component.md
When build_review_packet runs
Then spec_diff contains the actual diff text for that file
```
