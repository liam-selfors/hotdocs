# AC-KJS-007

Covers: R-KJS-005
Kind: generated-test

```gherkin
Given tmp_path / "secret.txt" holding "s3cret"
And tmp_path / "m.js" holding exactly
  "import { readFileSync } from 'node:fs';\n"
  "export function home() { return process.env.HOME ?? null; }\n"
  "export function peek(p) { return readFileSync(p, 'utf8'); }\n"
And os.environ["HOME"] set to "/home/x" with monkeypatch.setenv
And run = asset_runner(tmp_path / "m.js")
When run is called
Then run("home", []) is None (only PATH reaches the process)
And run("peek", [str(tmp_path / "secret.txt")]) raises AssetError
  whose message matches "restricted" (pytest.raises(AssetError,
  match="restricted"))
And after rewriting m.js as
  "export function home() { return 'new'; }\n", the same run returns
  "new" for run("home", []) (the file is copied at call time)
```
