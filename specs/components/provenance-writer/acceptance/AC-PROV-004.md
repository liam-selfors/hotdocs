# AC-PROV-004

Covers: R-PROV-004
Kind: compiled

```gherkin
Given ProvenanceInputs with provenance_hit true
When write_provenance runs
Then the manifest's provenance_hit is true
```
