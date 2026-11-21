# `ProvisionResult`

```json
{"ok": true, "reason": "",
 "versions": {"python": "3.14.6", "packages": "sha256:fe2b..."},
 "lockfile_sha256": null, "interpreter": "/usr/local/bin/python3"}
```

A plain `dict` with exactly these five keys.

- `ok`: `true` exactly when the environment is ready.
- `reason`: `""` when `ok`; otherwise one of the messages `R-KPY-005`
  states.
- `versions`: when `ok`, the decoded output of the environment
  program (`R-KPY-004`): `"python"` the interpreter's full version,
  `"packages"` the hash of its installed distributions; `{}` otherwise.
- `lockfile_sha256`: `"sha256:"` plus the lowercase hex SHA-256 of the
  lock's bytes whenever the lock exists, `ok` or not; `null` without one.
- `interpreter`: the absolute path, as a `str`, of the Python that runs
  the component's tests when `ok`; `null` otherwise.
