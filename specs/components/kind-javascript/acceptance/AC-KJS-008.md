# AC-KJS-008

Covers: R-KJS-004
Kind: generated-test

```gherkin
Given Node 24 or later on PATH
When provision(tmp_path) is called
Then the result has exactly the keys "ok", "reason", "versions",
  "lockfile_sha256", with ok True, reason "", lockfile_sha256 None,
  versions a dict whose only key is "node" and whose value matches
  ^\d+\.\d+\.\d+$ with an integer major part of 24 or more
And tmp_path is still empty afterwards
```
