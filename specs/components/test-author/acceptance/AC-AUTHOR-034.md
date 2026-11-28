# AC-AUTHOR-034

Covers: R-AUTHOR-029
Kind: generated-test

```gherkin
Given a spec-bundle-assembler stand-in planted at
  <repo_root>/gen/spec-bundle-assembler/spec_bundle_assembler.py whose
  assemble_criterion raises Exception("unknown component id: comp-a"),
  and author_test replaced by a stub that records each call
When main(["comp-a", "AC-A-001", "--model=m", "--repo-root=<repo_root>"])
  runs
Then it returns 1 without raising, stdout is empty, stderr is exactly
  "AC-A-001: cannot build its bundle: unknown component id: comp-a\n",
  and the stub was never called
```
