# AC-PROVCHECK-016

Covers: R-PROVCHECK-011
Kind: generated-test

Fixture, P and E: `testing.md`. The manifest has spec_bundle_hash H,
spec_bundle_parts {"spec": "S", "dependency_code": "D"}, gate_versions {}
and assets E.

```gherkin
Given that manifest
When check_provenance("comp-foo", "H2", {}, repo_root,
  {"spec": "S", "dependency_code": "D2"}) is called
Then hit is false and reason is "dependency code differs"

Given, separately, the parts P2 = {"spec": "S2", "dependency_code":
  "D2"}; P2 = None; the manifest has no spec_bundle_parts and P2 =
  {"spec": "S", "dependency_code": "D2"}
When check_provenance("comp-foo", "H2", {}, repo_root, P2) is called
Then reason is "spec_bundle_hash differs"

Given that manifest
When check_provenance("comp-foo", "H2", {"verifier": "v@1"}, repo_root,
  {"spec": "S", "dependency_code": "D2"}) is called
Then reason is "dependency code differs", a verifier change being one
  the committed code is re-verified for

Given that manifest
When check_provenance("comp-foo", "H2", {"generator": "g@2"}, repo_root,
  {"spec": "S", "dependency_code": "D2"}) is called
Then reason is "spec_bundle_hash differs"

Given that manifest
When check_provenance("comp-foo", "H", {}, repo_root,
  {"spec": "S", "dependency_code": "D2"}) is called
Then hit is true
```
