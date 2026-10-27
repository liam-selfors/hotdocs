# AC-PACKET-007

Covers: R-PACKET-007
Kind: generated-test

```gherkin
Given a PR that newly marks a component sealed: true
When build_review_packet runs
Then exemption_changes.sealed includes that component
```
