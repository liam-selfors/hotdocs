# AC-PROVCHECK-003

Covers: R-PROVCHECK-003
Kind: generated-test

```gherkin
Given gen/comp-foo/.provenance.json does not exist
When check_provenance is called for comp-foo with any spec_bundle_hash
Then the result's hit is false
```
