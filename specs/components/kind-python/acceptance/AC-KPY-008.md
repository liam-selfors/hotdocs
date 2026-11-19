# AC-KPY-008

Covers: R-KPY-005
Kind: generated-test

The one criterion that creates an environment, offline (`testing.md`
"A local lock"). `env` is `tmp_path / ".hotdocs" / "env" / "python"`
`h` is `"sha256:"` plus the hex SHA-256 of the lock's bytes at the
time of each call, `v` is `platform.python_version()`, and
`envinfo` is as `testing.md` states.

```gherkin
Given the lock holding exactly "--no-index\nPyTest==99.0.0\n"
When provision(tmp_path) is called
Then the result is exactly {"ok": False,
  "reason": "python environment: ERROR: No matching distribution found for PyTest==99.0.0",
  "versions": {}, "interpreter": None, "lockfile_sha256": h}
And env / "bin" / "python" exists, env / ".lock-sha256" does not, and
  tmp_path / ".hotdocs" / "env" / "python.lock" exists

Given the lock rewritten as the local lock of testing.md
When provision(tmp_path) is called twice
Then each result is exactly {"ok": True, "reason": "",
  "versions": envinfo(str(env / "bin" / "python")),
  "lockfile_sha256": h, "interpreter": str(env / "bin" / "python")}
And env / ".lock-sha256" holds exactly h + " " + v
And after (env / ".lock-sha256").write_text("stale"), provision(tmp_path)
  gives that same result again and the marker holds h + " " + v again
  (the environment was rebuilt)
```
