# AC-PROV-019

Covers: R-PROV-019
Kind: generated-test

```gherkin
Given a repo_root already holding a valid pipeline/foo/.sealed-provenance.json
When write_sealed_provenance is called with source_path "../escape/", or
  "gen/foo/", or "/abs/path/", with owners [], or with an owner "Alice",
  or with source_hash "sha256:abc", or with verifier_version "v2", or
  with a verification_report whose criteria list is empty, or with the
  component_id argument "comp-bar" while the inputs say "comp-foo", or
  with source_hash missing
Then each call raises InvalidSealedInputError, and the existing
  manifest's bytes are unchanged

Given a report whose overall is "pass" but one criteria entry has
  result "fail"
When write_sealed_provenance runs
Then InvalidSealedInputError is raised and no file is written
```
