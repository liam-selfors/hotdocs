# AC-PACKET-005

Covers: R-PACKET-005
Kind: generated-test

```gherkin
Given clean license-scan and secret-scan results
When build_review_packet runs
Then compliance_flags is present with both fields explicitly empty, not
  omitted
```
