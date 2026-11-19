# Testing provenance-checker

## The fake `python` adapter

Every criterion's `repo_root` plants `<repo_root>/gen/kind-python/kind_python.py`
(`D344`), so no criterion depends on the real adapter or the running
environment: it defines `KIND = "python"`, `guidance()` returning
`{"generator": "", "test_author": ""}`, and a deterministic
`provision(repo_root)` returning exactly
`{"ok": True, "reason": "", "versions": {"python": "3.12.0"}, "lockfile_sha256": None, "interpreter": "/fake/python"}`;
it is varied and observed as the fake kind's adapter is below. No
`asset-kind-python.md` is planted, so the expected python entry P is
`{"kind": "python", "path": ".", "definition_sha256": null, "adapter_sha256": PA, "versions": {"python": "3.12.0"}, "lockfile_sha256": null}`,
PA being `"sha256:"` plus the lowercase hex SHA-256 of `kind_python.py`'s
bytes. Every manifest a scenario expects to hit, and that gives no
`assets` of its own, has `assets` `[P]`, the current value of a
component that declares none.

## A fake asset kind

Criteria about assets (`AC-PROVCHECK-014`) plant a kind `fake` under a
temporary `repo_root`, so no real environment (Node) is needed:

- `<repo_root>/specs/architecture/asset-kind-fake.md`: any fixed text; its bytes'
  SHA-256 is the expected `definition_sha256`.
- `<repo_root>/gen/kind-fake/kind_fake.py`: defines `KIND = "fake"`,
  `guidance()` returning `{"generator": "G.", "test_author": "T."}`, and
  a deterministic `provision(repo_root)` returning a dict with exactly
  `ok`, `reason`, `versions`, `lockfile_sha256`, e.g.
  `{"ok": True, "reason": "", "versions": {"fakec": "2.0.0"}, "lockfile_sha256": None}`.
  To vary the result, rewrite the file before the call (the checker
  loads it by path afresh). To observe calls, have `provision` append a
  line to a file outside `repo_root` whose path is written into the
  module's source. Its bytes' SHA-256 is the expected `adapter_sha256`;
  compute both expected hashes after the last rewrite.
- `<repo_root>/specs/components/foo/component.md`: frontmatter with
  `id: comp-foo` and `assets: [fake:static/a.fake]`. The asset file
  itself need not exist: the checker never reads it.
- `<repo_root>/gen/foo/.provenance.json`: the manifest, with
  `spec_bundle_hash`, `gate_versions` `{}`, `verification_report`
  `{"criteria": []}`, `license_scan` and `secret_scan` `{}`, and
  `assets` as the scenario gives.

Unless a scenario says otherwise, `provision` reports `ok` true and
`versions` `{"fakec": "2.0.0"}`, and the expected assets value E is
`[P, {"kind": "fake", "path": "static/a.fake", "definition_sha256": D, "adapter_sha256": A, "versions": {"fakec": "2.0.0"}, "lockfile_sha256": null}]`,
D and A being `"sha256:"` plus the lowercase hex SHA-256 of `asset-kind-fake.md`'s
and `kind_fake.py`'s bytes.

For `current_provenance_key`, also plant the dependency stand-ins
`interface/library.md` lists, as `AC-PROVCHECK-009` does.

A kind named in no `specs/asset-kinds/` file and no `gen/kind-<kind>/`
directory, here or in the tool, is unknown (`nokind`).
