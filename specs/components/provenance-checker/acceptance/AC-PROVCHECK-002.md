# AC-PROVCHECK-002

Covers: R-PROVCHECK-003
Kind: compiled

```gherkin
Given gen/comp-foo/.provenance.json exists with spec_bundle_hash H
When check_provenance is called for comp-foo with a different
  spec_bundle_hash
Then the result's hit is false and verification_report, license_scan,
  and secret_scan are all null
```
