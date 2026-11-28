# AC-PROVCHECK-017

Covers: R-PROVCHECK-010
Kind: generated-test

Fixture, P, E and DR: `testing.md`. The manifest has spec_bundle_hash
H, gate_versions {}, assets E and drivers [DR].

```gherkin
Given fakedrv.json's versions becoming {"fakedrv": "2.1"}
When check_provenance("comp-foo", "H", {}, repo_root) is called
Then hit is false and reason is "environment differs"

Given a comment line appended to driver_fake.py, and separately a
  manifest with no drivers field
When check_provenance is called
Then reason is "drivers differ"

Given nothing changed
When current_provenance_key("comp-foo", repo_root) is called
Then its drivers is [DR], and check_provenance's hit is true
```
