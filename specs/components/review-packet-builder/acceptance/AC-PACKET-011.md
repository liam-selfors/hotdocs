# AC-PACKET-011

Covers: R-PACKET-011
Kind: generated-test

```gherkin
Given provenance-tracker's check_readiness reports comp-foo as a
  provenance hit with its VerificationReport and LicenseScanResult, a
  top-level secret_scan flagged with one match, and reports P-ZERO-EDIT as an intersecting
  capability with a CapabilityScenarioReport
When build_review_packet runs
Then verification_results, compliance_flags, provenance_hit_status,
  and capability_scenarios are all populated entirely from that
  VerifyReport, with no call made into verifier-orchestrator,
  license-scanner, secret-scanner, or capability-scenario-verifier
```
