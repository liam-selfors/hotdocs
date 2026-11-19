# `SurfaceReport`

```json
{
  "ok": false,
  "findings": [
    {"kind": "dependency_name", "message": "bar has no fetch_all, which the candidate uses"}
  ]
}
```

A dataclass with these fields in this order, with a `to_dict()` giving
the JSON form. `ok` is `true` exactly when `findings` is empty; each
finding is a plain dict with `kind` (`environment`, `import_error`, `dependency_name`,
`cli_usage`, `asset_error` or `asset_name_missing`) and `message`.
