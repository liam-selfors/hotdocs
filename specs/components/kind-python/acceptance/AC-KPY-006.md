# AC-KPY-006

Covers: R-KPY-004
Kind: generated-test

```gherkin
Given tmp_path with no environments/python/requirements.lock
When provision(tmp_path) is called
Then the result is exactly {"ok": True, "reason": "",
  "versions": {"python": platform.python_version()},
  "lockfile_sha256": None, "interpreter": sys.executable}
  (the test runs under the same Python as the module)
And tmp_path is still empty afterwards
```
