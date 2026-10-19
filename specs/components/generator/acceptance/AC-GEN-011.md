# AC-GEN-011

Covers: R-GEN-005
Kind: generated-test

```gherkin
Given a cache-manager pre-populated with a result for seed=0 and no
  retry_feedback, and the same spec_bundle_hash/gate_version/model_pin
When generate is called with seed=0 and retry_feedback=["R-FOO-003"]
Then this is a cache miss — the mock model is called — because
  gate_inputs_hash differs when retry_feedback is present, even though
  seed is unchanged
```
