# AC-PROV-002

Covers: R-PROV-002
Kind: compiled

```gherkin
Given a GenerationResult with model "claude-sonnet-5" and
  prompt_version "v1"
When write_provenance runs
Then model_pin is "claude-sonnet-5" and prompt_version is "v1" — with no
  sample_index or retry_feedback field present anywhere in the written
  manifest
```
