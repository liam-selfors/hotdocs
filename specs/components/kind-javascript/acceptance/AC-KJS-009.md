# AC-KJS-009

Covers: R-KJS-004
Kind: generated-test

```gherkin
Given PATH set to an empty directory (testing.md)
When provision(tmp_path) is called
Then the result is exactly {"ok": False,
  "reason": "javascript needs node >= 24", "versions": {},
  "lockfile_sha256": None}
And asset_runner(<any .js file>)("f", []) raises AssetError whose str
  is exactly "javascript needs node >= 24"
And with PATH set to a directory holding only a fake node printing
  "v18.2.0" (testing.md), provision gives exactly that same result
And with a fake node printing "hello", provision gives ok False,
  versions {} and reason exactly
  "javascript environment: node --version printed hello"
```
