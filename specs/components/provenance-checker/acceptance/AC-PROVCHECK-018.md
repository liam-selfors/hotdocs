# AC-PROVCHECK-018

Covers: R-PROVCHECK-012
Kind: generated-test

Fixture, P and E: `testing.md`. `repo_root` is also a git repository:
`git init -q`, then every git command run with `cwd=repo_root` as
`git -c user.name=t -c user.email=t@example.com -c commit.gpgsign=false ...`.
The manifest has spec_bundle_hash H, no spec_bundle_parts,
gate_versions {"verifier": "v@1"} and assets E; it and
specs/components/foo/ (with requirements/R-FOO-001.md holding the text
"x") are committed together.

```gherkin
Given that committed repo
When check_provenance("comp-foo", "H2", {"verifier": "v@2"}, repo_root)
  is called
Then reason is "hash formula differs"

Given that repo with R-FOO-001.md's text changed to "y" in the working
  tree, uncommitted
When the same call is made
Then reason is "spec_bundle_hash differs"

Given that committed repo, and separately a copy of it whose
  .provenance.json is modified in the working tree, and separately a
  copy with no .git directory
When check_provenance("comp-foo", "H2", {"generator": "g@2"}, repo_root)
  is called on the first, and check_provenance("comp-foo", "H2",
  {"verifier": "v@2"}, repo_root) on each copy
Then every reason is "spec_bundle_hash differs"
```
