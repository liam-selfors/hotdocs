# AC-GEN-018

Covers: R-GEN-017
Kind: generated-test

```gherkin
Given a SpecBundle with a known spec_bundle_hash, and a mock model that
  returns valid file content
When generate is called with that bundle
Then the returned GenerationResult's spec_bundle_hash field equals the
  bundle's own spec_bundle_hash exactly
```
