# AC-KJS-006

Covers: R-KJS-006
Kind: generated-test

```gherkin
Given tmp_path / "m.js" holding exactly
  "export function boom(m) { throw new Error('bad: ' + m); }\n"
  "export function plain() { throw 'plain text'; }\n"
  "export const notfn = 3;\n"
And run = asset_runner(that path)
When run is called with failing entries
Then run("boom", ["x"]) raises AssetError whose str is exactly "bad: x"
And run("plain", []) raises AssetError whose str is exactly "plain text"
And run("missing", []) raises AssetError whose str is exactly
  "no export missing"
And run("notfn", []) raises AssetError whose str is exactly
  "no export notfn"
```
