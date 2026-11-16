# AC-PROV-013

Covers: R-PROV-013
Kind: generated-test

```gherkin
Given ProvenanceInputs with component_id "comp-foo" and attempts 2
When write_provenance runs
Then the manifest's verification_run_id is "foo-attempt-2"

Given the exact same ProvenanceInputs run through write_provenance a
  second time
When the two manifests are compared
Then their verification_run_id fields are identical
```
