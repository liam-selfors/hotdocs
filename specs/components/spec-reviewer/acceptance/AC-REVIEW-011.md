# AC-REVIEW-011

Covers: R-REVIEW-009
Kind: generated-test

```gherkin
Given testing.md's synthetic corpus, and a stand-in
  spec-bundle-assembler at
  <repo_root>/gen/spec-bundle-assembler/spec_bundle_assembler.py whose
  assemble_criterion raises Exception("unknown asset kind: css")
When check(["comp-foo"], repo_root) runs with no model, and then
  main(["comp-foo", "--repo-root", <repo_root>]) runs
Then check returns without raising, its findings are exactly one,
  criterion_id "AC-FOO-001", kind "bundle_unavailable", token "",
  message "AC-FOO-001: its bundle cannot be built: unknown asset kind: css",
  its writable is {"AC-FOO-001": None}, and main returns 1
```
