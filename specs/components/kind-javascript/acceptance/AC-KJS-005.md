# AC-KJS-005

Covers: R-KJS-006
Kind: generated-test

```gherkin
Given tmp_path / "m.js" holding exactly
  "export function add(a, b) { return a + b; }\n"
  "export function nothing() {}\n"
  "export async function later(x) { return [x, {k: null}, true]; }\n"
  "export function noisy() { console.log('hi'); return 'ok'; }\n"
And run = asset_runner(that path)
When run is called
Then run("add", [1, 2]) == 3 and run("add", ["a", "b"]) == "ab"
And run("nothing", []) is None
And run("later", [5]) == [5, {"k": None}, True]
And run("noisy", []) == "ok"
```
