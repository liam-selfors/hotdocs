# AC-LICENSE-004

Covers: R-LICENSE-004
Kind: generated-test

```gherkin
Given cache-manager already holds a result for the exact
  (spec_bundle_hash, gen_output_hash, gate_version, model_pin) key
When license-scan runs with matching inputs
Then the cached result is returned and no rescan is performed
```
