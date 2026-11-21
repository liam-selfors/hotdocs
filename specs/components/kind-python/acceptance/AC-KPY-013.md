# AC-KPY-013

Covers: R-KPY-004
Kind: generated-test

The interpreter pin (`D345`). `pv` is `platform.python_version()` and
`mm` is `"%d.%d" % sys.version_info[:2]`; the tests run on Python 3.11
or later, so `"3.1"` is a prefix of `pv`'s text but not of its version.

```gherkin
Given tmp_path / "environments" / "python" / "python-version" holding
  mm + "\n", and no lock
When provision(tmp_path) is called
Then ok is True, reason "" and interpreter sys.executable
And the same holds with the pin file holding exactly pv

Given the pin file holding "3.1\n", and no lock
When provision(tmp_path) is called
Then the result is exactly {"ok": False,
  "reason": "python environment: needs Python 3.1, found " + pv,
  "versions": {}, "lockfile_sha256": None, "interpreter": None}

Given the pin file holding "2.7", and the lock holding exactly
  "--no-index\npytest==8.0.0\n"
When provision(tmp_path) is called
Then the result is exactly {"ok": False,
  "reason": "python environment: needs Python 2.7, found " + pv,
  "versions": {}, "interpreter": None,
  "lockfile_sha256": "sha256:" + hashlib.sha256(<the lock's bytes>).hexdigest()}
And tmp_path / ".hotdocs" does not exist afterwards
```
