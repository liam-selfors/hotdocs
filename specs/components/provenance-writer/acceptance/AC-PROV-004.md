# AC-PROV-004

Covers: R-PROV-004
Kind: compiled

```gherkin
Given a GenerationResult with cache_hit true
When write_provenance runs
Then the manifest's cache_hit is true
```
