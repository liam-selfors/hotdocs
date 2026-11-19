# AC-VERIFY-031

Covers: R-VERIFY-020
Kind: generated-test

```gherkin
Given comp-qux declaring assets: [fake:data/table.txt] with the fake
  kind planted, and one cached passing generated test
When verify runs
Then report.assets == [{"kind": "fake", "path": "data/table.txt",
  "definition_sha256": D, "adapter_sha256": A, "versions": {"fake": "1.0"},
  "lockfile_sha256": None}], D and A being "sha256:" plus the lowercase
  hex SHA-256 of specs/asset-kinds/fake.md's and
  gen/kind-fake/kind_fake.py's bytes

Given comp-qux declares no assets
When verify runs
Then report.assets == []
```
