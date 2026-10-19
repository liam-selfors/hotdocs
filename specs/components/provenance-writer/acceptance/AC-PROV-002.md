# AC-PROV-002

Covers: R-PROV-002
Kind: compiled

```gherkin
Given a GenerationResult with model "claude-sonnet-5", seed 2, and
  retry_feedback ["R-FOO-002"]
When write_provenance runs
Then model_pin is "claude-sonnet-5", sample_index is 2, and
  retry_feedback is ["R-FOO-002"]
```
