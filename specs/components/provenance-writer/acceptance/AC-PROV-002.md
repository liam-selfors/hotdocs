# AC-PROV-002

Covers: R-PROV-002
Kind: compiled

```gherkin
Given a GenerationResult with model "claude-sonnet-5", prompt_version
  "v1", and retry_feedback ["R-FOO-002"]
When write_provenance runs
Then model_pin is "claude-sonnet-5", prompt_version is "v1",
  retry_feedback is ["R-FOO-002"], and no sample_index field is present
  anywhere in the written manifest
```
