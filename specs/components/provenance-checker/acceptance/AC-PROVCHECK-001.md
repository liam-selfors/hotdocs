# AC-PROVCHECK-001

Covers: R-PROVCHECK-002
Kind: generated-test

```gherkin
Given gen/comp-foo/.provenance.json exists with spec_bundle_hash H, and
  its verification_report has no llm-judge-kind criteria
When check_provenance is called for comp-foo with spec_bundle_hash H
Then the result's hit is true and verification_report, license_scan,
  and secret_scan match the committed manifest exactly
```
