# AC-GEN-005

Covers: R-GEN-005
Kind: generated-test

```gherkin
Given a cache-manager pre-populated with a result for a given
  (spec_bundle_hash, gate_inputs_hash, gate_version, model_pin) key
When generate is called with inputs matching that key
Then the cached result is returned and the mock model is never called
```
