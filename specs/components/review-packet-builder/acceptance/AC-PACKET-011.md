# AC-PACKET-011

Covers: R-PACKET-011
Kind: compiled

```gherkin
Given comp-foo's provenance manifest at
  verification/comp-foo/.provenance.json already contains its
  VerificationReport, LicenseScanResult, SecretScanResult, and
  provenance_hit
When build_review_packet runs
Then verification_results, compliance_flags, and provenance_hit_status
  for comp-foo are populated entirely from that manifest via the
  component_provenance view, with no call made into verifier-orchestrator,
  license-scanner, or secret-scanner
```
