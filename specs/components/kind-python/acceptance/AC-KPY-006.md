# AC-KPY-006

Covers: R-KPY-004
Kind: generated-test

```gherkin
Given tmp_path with no environments/python/requirements.lock
When provision(tmp_path) is called
Then the result is exactly {"ok": True, "reason": "",
  "versions": envinfo(sys.executable),
  "lockfile_sha256": None, "interpreter": sys.executable}
  (envinfo as testing.md states; versions["python"] ==
  platform.python_version())
And tmp_path is still empty afterwards
```
