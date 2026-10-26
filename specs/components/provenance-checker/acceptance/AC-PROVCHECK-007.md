# AC-PROVCHECK-007

Covers: R-PROVCHECK-001
Kind: compiled

```gherkin
Given gen/comp-foo/.provenance.json exists with spec_bundle_hash H
When check_provenance is called for comp-foo with a caller-supplied
  spec_bundle_hash
Then the comparison uses exactly the caller-supplied hash against the
  manifest's own spec_bundle_hash field — this component never computes
  a spec_bundle_hash of its own
```
