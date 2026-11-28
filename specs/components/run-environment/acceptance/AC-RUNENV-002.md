# AC-RUNENV-002

Covers: R-RUNENV-002
Kind: generated-test

```gherkin
Given the fake kind declared
When prepare("comp-foo", repo_root) is called
Then assets has two entries: first kind "python", path ".", and the real
  adapter's versions; then kind "fake", path "data/table.txt",
  definition_sha256 the hash of asset-kind-fake.md, adapter_sha256 the
  hash of kind_fake.py, versions {"fake": "1.0"} and lockfile_sha256
  None, each hash "sha256:" and the file's lowercase hex SHA-256

Given "assets: [nokind:x.txt]"
When prepare is called
Then assets' second entry has kind "nokind", adapter_sha256 None,
  definition_sha256 None, versions {} and lockfile_sha256 None
```
