# AC-PROV-009

Covers: R-PROV-009
Kind: generated-test

```gherkin
Given ProvenanceInputs with provenance_hit true, carrying
  verification_report/license_scan/secret_scan already sourced from a
  prior manifest by the caller
When write_provenance runs
Then those three fields are written verbatim, unchanged, with no
  lookup performed by this component itself
```
