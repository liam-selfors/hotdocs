# `ProvisionResult`

```json
{"ok": true, "reason": "", "versions": {"node": "24.1.0"}, "lockfile_sha256": null}
```

A plain `dict` with exactly these four keys.

- `ok`: `true` exactly when `node --version` printed a version whose
  major part is 24 or more.
- `reason`: `""` when `ok`; otherwise one of the messages
  `R-KJS-004` states.
- `versions`: `{"node": "<x.y.z>"}` when `ok`, the version as printed
  without its leading `v`; `{}` otherwise.
- `lockfile_sha256`: always `null` (`None`); the kind has no lockfile.
