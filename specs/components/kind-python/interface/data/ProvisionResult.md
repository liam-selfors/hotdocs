# `ProvisionResult`

```json
{"ok": true, "reason": "", "versions": {"python": "3.14"},
 "lockfile_sha256": null, "interpreter": "/usr/local/bin/python3"}
```

A plain `dict` with exactly these five keys.

- `ok`: `true` exactly when the environment is ready.
- `reason`: `""` when `ok`; otherwise one of the messages `R-KPY-005`
  states.
- `versions`: `{"python": "<major>.<minor>"}` when `ok`, as the
  interpreter printed it; `{}` otherwise.
- `lockfile_sha256`: `"sha256:"` plus the lowercase hex SHA-256 of the
  lock's bytes whenever the lock exists, `ok` or not; `null` without one.
- `interpreter`: the absolute path, as a `str`, of the Python that runs
  the component's tests when `ok`; `null` otherwise.
