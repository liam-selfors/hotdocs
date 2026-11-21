# AC-KPY-003

Covers: R-KPY-003
Kind: generated-test

```gherkin
Given tmp_path / "my-mod" / "my_mod.py" holding exactly
  "import os\nfrom json import dumps\n\nALPHA = 1\n_hidden = 2\n\n\ndef beta():\n    return 3\n\n\nclass Gamma:\n    pass\n"
When surface(tmp_path / "my-mod") is called
Then the result is exactly
  {"names": ["ALPHA", "Gamma", "beta", "dumps", "os"]}
And with tmp_path / "pk" / "pk" / "__init__.py" holding
  "from .sub import val\n" and tmp_path / "pk" / "pk" / "sub.py"
  holding "val = 1\n", surface(tmp_path / "pk") is exactly
  {"names": ["sub", "val"]}
And with tmp_path / "bad" / "bad.py" holding
  "raise RuntimeError('no')\n", surface(tmp_path / "bad") is exactly
  {"names": []}
```
