# AC-KPY-005

Covers: R-KPY-006
Kind: generated-test

```gherkin
Given tmp_path / "calc" / "calc.py" holding exactly
  "def boom(m):\n    raise ValueError('bad: ' + m)\n\n\n"
  "def unjson():\n    return {1, 2}\n\n\n"
  "NOTFN = 3\n"
And run = asset_runner(tmp_path / "calc")
When run is called with failing entries
Then run("boom", ["x"]) raises AssetError whose str is exactly "bad: x"
And run("unjson", []) raises AssetError whose str is exactly
  "Object of type set is not JSON serializable"
And run("missing", []) raises AssetError whose str is exactly
  "no entry missing"
And run("NOTFN", []) raises AssetError whose str is exactly
  "no entry NOTFN"
```
