# AC-PROV-012

Covers: R-PROV-012
Kind: generated-test

```gherkin
Given two separate write_provenance calls, each with different
  ProvenanceInputs
When each manifest is written
Then both manifests' pipeline_version fields are identical, and equal
  this component's own version constant
```
