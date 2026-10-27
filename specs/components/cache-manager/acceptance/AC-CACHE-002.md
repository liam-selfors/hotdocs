# AC-CACHE-002

Covers: R-CACHE-002
Kind: generated-test

```gherkin
Given the same four key components (spec_bundle_hash, gate_inputs_hash,
  gate_version, model_pin) supplied by two different calling components
When each computes the cache key for a put
Then both produce byte-identical serialized keys
```
