# `ProbeReport`

```json
{
  "ok": false,
  "findings": [
    {"kind": "undefined_name", "severity": "error", "line": 12,
     "message": "undefined name 'tmp_dir'"},
    {"kind": "vacuous", "severity": "warn", "line": null,
     "message": "test_defaults passed without reaching the code under test"}
  ],
  "tests_run": 3,
  "tests_reached": 2
}
```

A dataclass with these fields in this order, with a `to_dict()` giving
the JSON form. `findings` is a plain `list` of plain `dict`s, each with
exactly the keys `kind`, `severity`, `line` and `message`, so
`report.findings[0]["kind"]` and `report.to_dict()["findings"]` agree. `ok` is `true` exactly when no finding has severity
`error`. `line` is the 1-based source line, or `null` when the finding
has none. `tests_run` and `tests_reached` count `testcase` elements, and
those that reached the code under test; both are `0` when no stub run
happened.

| `kind` | `severity` | Meaning |
| --- | --- | --- |
| `syntax_error` | `error` | the source does not parse |
| `undefined_name` | `error` | pyflakes reports a name used but never defined |
| `unknown_import` | `error` | an import that resolves to nothing |
| `fake_signature_mismatch` | `error` | a fake's parameter count differs from the interface |
| `collection_error` | `error` | pytest could not collect the file |
| `test_bug` | `error` | a test failed before reaching the code under test |
| `probe_timeout` | `error` | the stub run exceeded `timeout` |
| `vacuous` | `warn` | a test passed without reaching the code under test |
