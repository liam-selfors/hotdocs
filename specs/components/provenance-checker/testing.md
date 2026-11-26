# Testing provenance-checker

## The fake `python` adapter

Every criterion's `repo_root` plants `<repo_root>/gen/kind-python/kind_python.py`
(`D344`), so no criterion depends on the real adapter or the running
environment: it defines `KIND = "python"`, `guidance()` returning
`{"generator": "", "test_author": ""}`, and a deterministic
`provision(repo_root)` returning exactly
`{"ok": True, "reason": "", "versions": {"python": "3.12.4", "packages": PK}, "lockfile_sha256": None, "interpreter": "/fake/python"}`,
PK being `"sha256:"` plus 64 `a`s (`D345`'s shape);
it is varied and observed as the fake kind's adapter is below. No
`asset-kind-python.md` is planted, so the expected python entry P is
`{"kind": "python", "path": ".", "definition_sha256": null, "adapter_sha256": PA, "versions": {"python": "3.12.4", "packages": PK}, "lockfile_sha256": null}`,
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
  loads it by path afresh). To vary only `versions` or
  `lockfile_sha256` (`AC-PROVCHECK-015`), which must leave the
  adapter's bytes and so `adapter_sha256` unchanged, `provision` reads
  those two values, when present, from a JSON file outside `repo_root`
  whose path is written into the module's source; the test rewrites
  that file between calls. Both fakes work so. To observe calls, have `provision` append a
  line to a file outside `repo_root` whose path is written into the
  module's source. Its bytes' SHA-256 is the expected `adapter_sha256`;
  compute both expected hashes after the last rewrite.
- `<repo_root>/specs/components/foo/component.md`: frontmatter with
  `id: comp-foo` and `assets: [fake:static/a.fake]`, and never
  `sealed: true` unless a scenario is about a sealed component (a
  sealed component's assets value is `[]` and no adapter is called,
  `R-PROVCHECK-009`). A scenario with no fake kind omits the `assets`
  line; the checker reads only this frontmatter, so nothing else is
  needed. The asset file itself need not exist.
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

## Stand-ins

Every dependency is loaded afresh on each call, so a stand-in that
records its calls does so through a side channel the test controls,
such as a file outside `repo_root` whose path is written into the
stand-in's source. A stand-in provides each name `interface/library.md`
lists for it (`verifier-orchestrator`'s `GATE_VERSION` included); a
stand-in `assemble` needs no `specs/` tree.

## Sealed manifests

`AC-PROVCHECK-012`/`013` use `AC-PROVCHECK-011`'s fixture and write the
manifest as JSON, taking `source_hash` from `current_sealed_key` unless
the scenario says otherwise. A valid manifest has kind
"sealed-provenance", version 1, component_id "comp-foo", owners
["pipeline-team", "alice"], source_path "pipeline/foo/",
verifier_version "verifier-orchestrator@2.0.0", characterization
{"overall": "pass", "criteria_passed": 2, "criteria_total": 2}, and
written_at "2026-11-02T00:00:00Z"; a valid, current one passes.

## Key stand-ins

`AC-PROVCHECK-009`'s `repo_root` has: spec-bundle-assembler, whose
`assemble` records its arguments and returns an object with
spec_bundle_hash "sha256:abc"; criterion-compiler (under
pipeline/criterion-compiler/), test-author and verifier-orchestrator,
defining GATE_VERSION "cc@1", "ta@1" and "vo@1"; license-scanner and
secret-scanner, each defining gate_version(repo_root) returning "ls@1"
and "ss@1" and a scan function that records any call; and generator,
defining GATE_VERSION "gen@3" and PROMPT_VERSION "v11".

## A fake test driver

Criteria about drivers (`AC-PROVCHECK-017`) plant
`<repo_root>/gen/driver-fake/driver_fake.py`, with no definition file,
defining `NAME = "fake"`, `FIXTURE = "fake_session"` and
`provision(repo_root)` returning, from the JSON file
`<repo_root>/fakedrv.json`, `{"ok": True, "reason": "", "versions": <its versions>, "lockfile_sha256": None}`,
the file initially `{"versions": {"fakedrv": "2.0"}}`; comp-foo's
frontmatter gains `drivers: [fake]`. Its expected entry DR is
`{"name": "fake", "definition_sha256": null, "adapter_sha256": DA, "versions": {"fakedrv": "2.0"}, "lockfile_sha256": null}`,
DA being `"sha256:"` plus the lowercase hex SHA-256 of `driver_fake.py`'s
bytes.
