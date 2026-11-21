# AC-KPY-004

Covers: R-KPY-006
Kind: generated-test

```gherkin
Given tmp_path / "calc" / "calc.py" holding exactly
  "def add(a, b):\n    return a + b\n\n\n"
  "def nothing():\n    pass\n\n\n"
  "def pair(x):\n    print('noise', end='')\n    return [x, {'k': None}, True]\n"
And run = asset_runner(tmp_path / "calc")
When run is called
Then run("add", [1, 2]) == 3 and run("add", ["a", "b"]) == "ab"
And run("nothing", []) is None
And run("pair", [5]) == [5, {"k": None}, True]
And after rewriting calc.py as "def add(a, b):\n    return 'new'\n",
  the same run returns "new" for run("add", [1, 2])
  (the code is read at call time)
And with HOTDOCS_PYTHON set to str(tmp_path / "nope") (monkeypatch.setenv),
  run("add", [1, 2]) raises AssetError whose str is exactly
  "cannot start " + str(tmp_path / "nope"), and
  surface(tmp_path / "calc") is exactly {"names": []}
```
