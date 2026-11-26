# AC-PROV-025

Covers: R-PROV-023
Kind: generated-test

```gherkin
Given valid ProvenanceInputs with spec_bundle_parts {"spec": "sha256:s",
  "dependency_code": "sha256:d"}
When write_provenance runs
Then the manifest's spec_bundle_parts is {"spec": "sha256:s",
  "dependency_code": "sha256:d"}

Given the same inputs without a spec_bundle_parts field
When write_provenance runs
Then the manifest's spec_bundle_parts is null
```
