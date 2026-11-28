# AC-PROVCHECK-019

Covers: R-PROVCHECK-013
Kind: generated-test

Fixture, P and E: `testing.md`. The manifest has spec_bundle_hash H,
gate_versions {"verifier": "v@1", "compiler": "c@1", "generator": "g@1"}
and assets E.

```gherkin
Given that manifest
When check_provenance("comp-foo", "H", {"verifier": "v@2", "compiler":
  "c@1", "generator": "g@1"}, repo_root) is called, and again with
  {"verifier": "v@2", "compiler": "c@2", "generator": "g@1"}
Then each reason is "gates differ"

Given that manifest
When check_provenance("comp-foo", "H", {"verifier": "v@2", "compiler":
  "c@1", "generator": "g@2"}, repo_root) is called
Then reason is "gate_versions differ"
```
