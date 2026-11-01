# AC-PROVCHECK-004

Covers: R-PROVCHECK-003
Kind: generated-test

```gherkin
Given gen/foo/.provenance.json exists with spec_bundle_hash H, its
  verification_report has an llm-judge-kind criterion, and
  VAR-TRUST-JUDGE-PROVENANCE is false
When check_provenance is called for comp-foo with spec_bundle_hash H
Then the result's hit is false
```
