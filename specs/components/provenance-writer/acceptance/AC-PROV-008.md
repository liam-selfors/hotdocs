# AC-PROV-008

Covers: R-PROV-008
Kind: compiled

```gherkin
Given a GenerationResult carrying an unrelated internal timestamp
When write_provenance runs
Then generated_at reflects this component's own write time, not that
  internal timestamp
```
