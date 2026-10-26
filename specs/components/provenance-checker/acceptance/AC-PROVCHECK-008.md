# AC-PROVCHECK-008

Covers: R-PROVCHECK-001
Kind: compiled

```gherkin
Given gen/comp-foo/.provenance.json exists with spec_bundle_hash H and
  gate_versions {"license_scanner": "1.0.0"}, but the caller's current
  gate_versions is {"license_scanner": "2.0.0"}
When check_provenance is called for comp-foo with spec_bundle_hash H
Then the result's hit is false, even though spec_bundle_hash matches
```
