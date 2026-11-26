# Testing run-environment

Every criterion writes its corpus under a fresh temporary `repo_root`.

**The component.** `specs/components/foo/component.md`, frontmatter
`id: comp-foo` and any `assets:` or `drivers:` line the criterion names,
then `# Foo`. Code under `gen/foo/` only when the criterion names it.

**The python kind.** A criterion not about `python` plants nothing, so
the tool root's real adapter is used:
`Path(run_environment.__file__).parents[1] / "kind-python" / "kind_python.py"`.
A test reads its expected entry by loading that file by path and calling
`provision(repo_root)`, never by writing versions out.

**A fake kind.** `<repo_root>/specs/architecture/asset-kind-fake.md`
(any text) and `<repo_root>/gen/kind-fake/kind_fake.py`, defining
`KIND = "fake"`, `asset_runner(asset_file)` returning `run(entry, args)`
that returns the integer after `<entry>=` on its line of the file, and
`provision(repo_root)` returning
`{"ok": True, "reason": "", "versions": {"fake": "1.0"}, "lockfile_sha256": None}`,
or, for an unprovisioned kind,
`{"ok": False, "reason": "fake needs fakeprog >= 2", "versions": {}, "lockfile_sha256": None}`.
The component declares `assets: [fake:data/table.txt]`, and
`gen/foo/data/table.txt` holds the two lines `a=1` and `b=2`.

**A fake driver.** `<repo_root>/gen/driver-fake/driver_fake.py`, with no
definition file, defining `NAME = "fake"`, `FIXTURE = "fake_session"`,
`guidance()` returning `{"test_author": "Fake driver text."}`,
`provision(repo_root)` returning
`{"ok": True, "reason": "", "versions": {"fakedrv": "2.0"}, "lockfile_sha256": None}`
(or, unprovisioned, `ok` False with `reason` `fake needs fakedrv >= 3`),
and `open_session(repo_root, work_dir)` returning an object whose
`value` is `"open"` and whose `close()` appends the line `closed` to
`<repo_root>/closed.log`. The component declares `drivers: [fake]`. A
driver or kind with no adapter (`nodrv`, `nokind`) is declared without
planting one.

A test running pytest on its own test file uses `interpreter`, the
working directory `repo_root`, `PYTHONPATH` `plugin_dir` and the
variables `env_for(repo_root / "gen" / "foo")` returns, and calls
`close()` at the end.
