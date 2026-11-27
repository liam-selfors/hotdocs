# AC-KCSS-007

Covers: R-KCSS-006
Kind: generated-test

```gherkin
Given testing.md's s.css and run = asset_runner(<its path>)
When run("contrast", ...) is called
Then run("contrast", ["--c-text", "--c-bg"]) == 15.8,
  run("contrast", ["--c-bg", "--c-text"]) == 15.8, and
  run("contrast", ["--c-text", "--c-bg", "dark"]) == 1.2
And run("contrast", ["--c-x", "--c-bg"]) raises AssetError
  "no token --c-x", and run("contrast", ["--c-gap", "--c-bg"]) raises
  AssetError "not a #rrggbb colour: --c-gap"
```
