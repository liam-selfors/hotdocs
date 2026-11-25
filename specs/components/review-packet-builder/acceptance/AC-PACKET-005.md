# AC-PACKET-005

Covers: R-PACKET-005
Kind: generated-test

```gherkin
Given clean license-scan and secret-scan results
When build_review_packet runs
Then compliance_flags is present with both fields explicitly empty, not
  omitted

Given check_readiness reports secret_scan {"flagged": false, "matches":
  []}, and one component whose stored secret_scan has flagged true
When build_review_packet runs
Then compliance_flags.secret_scan is []

Given check_readiness reports secret_scan S, {"flagged": true,
  "matches": [{"file": "a/b.py", "line": 3, "rule_id": "AWS Access
  Key", "risk_tier": "high"}]}
When build_review_packet runs
Then compliance_flags.secret_scan is exactly [{"component_id": null,
  "result": S}]
```
