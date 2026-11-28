# `RunEnvironment`

```json
{
  "ok": true,
  "failure_message": null,
  "interpreter": "/usr/bin/python3",
  "assets": [{"kind": "python", "path": ".", "definition_sha256": null,
              "adapter_sha256": "sha256:<hex>", "versions": {"python": "3.14.6"},
              "lockfile_sha256": null}],
  "drivers": [{"name": "browser", "definition_sha256": null,
               "adapter_sha256": "sha256:<hex>",
               "versions": {"playwright": "1.0.0", "chromium": "140.0"},
               "lockfile_sha256": null}],
  "plugin_dir": "/tmp/tmpabc123"
}
```

A dataclass with these fields, plus:

- `pytest_args() -> list[str]`: `["-p", "hotdocs_run_plugins"]`.
- `driver_fixtures() -> list[str]`: each declared driver adapter's
  `FIXTURE`, in `drivers` order.
- `env_for(code_dir: Path) -> dict[str, str]`: `HOTDOCS_ASSETS` and
  `HOTDOCS_DRIVERS` as `specs/architecture/run-environment.md` gives
  them, each asset's `file` being `<code_dir>/<path>`.
- `close() -> None`: removes `plugin_dir`; calling it again, or with
  `plugin_dir` null, does nothing.
- `to_dict()`: the JSON above.

`assets` entries are `VerificationReport.assets`' (`asset-kinds.md`,
Provenance); `drivers` entries are `VerificationReport.drivers`'
(`test-drivers.md`). When `ok` is false, `interpreter` and `plugin_dir`
are `null` and `pytest_args()` and `env_for` are never called.
