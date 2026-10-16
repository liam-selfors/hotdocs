# AC-PROV-002

Covers: R-PROV-002
Kind: compiled

```gherkin
Given a GenerationResult with model "claude-sonnet-5" and seed 2
When write_provenance runs
Then model_pin is "claude-sonnet-5" and sample_index is 2
```
