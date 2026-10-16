# AC-CACHE-005

Covers: R-CACHE-005
Kind: compiled

```gherkin
Given an entry stored under gate_version "license_scanner@1.0.0"
When get is called with the same spec_bundle_hash/gate_inputs_hash/model_pin
  but gate_version "license_scanner@2.0.0"
Then it returns Miss, not the entry stored under the old gate_version
```
