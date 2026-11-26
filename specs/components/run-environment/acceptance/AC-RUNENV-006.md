# AC-RUNENV-006

Covers: R-RUNENV-006
Kind: generated-test

```gherkin
Given the fake driver planted and specs/product/x.md with frontmatter
  "id: P-X" and "drivers: [fake]"
When prepare_capability("P-X", repo_root) is called
Then ok is true, assets holds the python entry alone, and drivers'
  one entry has name "fake" and versions {"fakedrv": "2.0"}

Given no product file with id P-Y
When prepare_capability("P-Y", repo_root) is called
Then ok is true and drivers is []
```
