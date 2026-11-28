# AC-PROVCHECK-015

Covers: R-PROVCHECK-010
Kind: generated-test

Fixture, P, PK and E: `testing.md`. The manifest has spec_bundle_hash
H, gate_versions {} and assets E; versions change only through the
fakes' JSON files. X is "sha256:" plus 64 "b"s.

```gherkin
Given separately: python's versions become {"python": "3.12.5",
  "packages": PK}; python's become {"python": "3.12.4", "packages": X};
  fake's become {"fakec": "2.1.0"}; fake's lockfile_sha256 becomes X;
  python's and fake's both change so
When check_provenance("comp-foo", "H", {}, repo_root) is called
Then hit is false and reason is "environment differs"

Given python's versions become {"python": "3.12.5", "packages": PK}
  and, separately: the definition file changes; the manifest's assets
  is [P]; is E reversed; has E's second entry appended; its fake entry
  has adapter_sha256 X; its fake entry lacks definition_sha256
When check_provenance is called
Then reason is "assets differ"

Given that version change and the manifest's gate_versions
  {"verifier": "v@0"}, and separately {"generator": "g@0"}
When check_provenance is called
Then the first reason is "gates differ" (R-PROVCHECK-013: a verifier
  change only) and the second is "gate_versions differ"

Given the versions set back
When check_provenance is called
Then hit is true
```
