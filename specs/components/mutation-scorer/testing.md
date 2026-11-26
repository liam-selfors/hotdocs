# Testing mutation-scorer

Every criterion writes its fixture under a fresh temporary `repo_root`:
`specs/components/qux/component.md` with frontmatter `id: comp-qux`
and any `assets:` line the criterion names, then `# Qux`; the code at
`gen/qux/qux.py`; and the test files the criterion names, each written
to a temporary directory outside `repo_root` and passed to `score` by
absolute path. A test file imports `qux` and asserts on it.

The environment is the real one: a test loads `run-environment` by
path from `Path(mutation_scorer.__file__).resolve().parents[1] /
"run-environment" / "run_environment.py"`, calls
`prepare("comp-qux", repo_root)`, passes the result, and calls its
`close()` at the end. The `python` kind is the tool's real adapter.

**A fake kind**, for a criterion about assets:
`<repo_root>/specs/architecture/asset-kind-fake.md` (any text) and
`<repo_root>/gen/kind-fake/kind_fake.py` defining `KIND = "fake"`;
`provision(repo_root)` returning
`{"ok": True, "reason": "", "versions": {"fake": "1.0"}, "lockfile_sha256": None}`;
`asset_runner(asset_file)` returning `run(entry, args)`, which reads the
file when called and returns the integer after `<entry>=` on its line;
`strength_sites(asset_file)` returning
`[{"description": "1: a"}, {"description": "2: b"}]`; and
`apply_site(asset_file, site)` adding 1 to the number on that site's
line. The component declares `assets: [fake:data/table.txt]` and
`gen/qux/data/table.txt` holds the two lines `a=1` and `b=2`.
