---
id: arch-verifier-fixtures
title: Verifier Fixtures
status: draft
owners: [pipeline-team]
depends_on: []
---

# Verifier Fixtures

## Purpose

How a test of `verifier-orchestrator` builds the synthetic corpus and
the stand-ins `verify` and its parts run against, and how a test run
reaches a declared asset (`specs/architecture/asset-kinds.md`, `D343`).

## Rules

A test plants a fake dependency at the path `verify` or `test-supply` loads it from:
`<repo_root>/gen/spec-bundle-assembler/spec_bundle_assembler.py`,
`<repo_root>/gen/test-probe/test_probe.py`, or
`<repo_root>/pipeline/criterion-compiler/criterion_compiler.py`. A fixture
component under test is never `sealed`, unless its criterion concerns
sealed verification (`R-VERIFY-017`): a sealed one runs only its
characterization tests, never its compiled or generated ones. An
unsealed fixture component lints clean only with `realizes: [P-<ID>]`
naming a capability file the fixture also writes under `specs/product/`
(`R-LINT-006`). Name fixture functions other than `foo`:
`spec-bundle-assembler`'s interface text declares `foo(x)`, which
`test-probe`'s fake-arity check would match. Every
fixture criterion has at least one Given, one When and one Then step
(`R-LINT-010`). `verify` checks no precondition against `spec-linter`,
so a test does not lint its fixture (`R-AUTHOR-015`). A
test's own helper functions are named without a `test` prefix
(`build_fixture`, `characterization_source`): pytest collects every
top-level `test*` function in the file, and one taking parameters it
has no fixture for errors the whole criterion (`D326`). Test functions
for a fixture's own suite are written only inside string literals.

A `test-probe` stand-in defines `probe(test_source, criterion_bundle,
module_name, *, timeout=60.0)` returning an object with `ok` (bool),
`findings` (a list of dicts with `kind`, `severity`, `line` and
`message`) and `to_dict()`. A fixture that does not concern probing
plants one returning `ok` true with no findings, so every test runs.

A test whose fixture has a `compiled` criterion supplies the compiler
in `repo_root`: a stand-in, or the real one copied to
`<repo_root>/pipeline/criterion-compiler/` from
`<live>/pipeline/criterion-compiler/`, where `<live>` is
`(Path(verifier_orchestrator.__file__).resolve().parents[1] /
"spec-bundle-assembler").resolve().parents[1]` (`D339`). It never
relies on `verify`'s fallback to the tool root: a mutation run's tool
root holds only `gen/` (`specs/architecture/mutation-runs.md`), while a
sibling `gen/` directory resolves to the tree the criterion run used.

A `spec-bundle-assembler` stand-in defines
`assemble_criterion(component_id, criterion_id, repo_root)`, the only
assembler function `verify` and `test-supply` call. Its return value, a
`CriterionBundle` or a mapping with its keys, is the bundle `test-supply`
hashes for the criterion header (`R-SUPPLY-001`), passes to `test_author`
and passes to `test-probe`'s `probe`. A test that needs a cached file's correct header plants such a
stand-in with known `criterion_text`, `requirement_text`, `interface`,
`glossary` and `testing` and writes the first line as
`# hotdocs-criterion: sha256:` followed by the SHA-256 hex of
`json.dumps({k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` encoded UTF-8
(`specs/architecture/test-reuse.md`, `D341`).
A header line is one matching
`^# hotdocs-criterion: sha256:[0-9a-f]{64}$`; any other first line,
including uppercase hex, is no header, so that file is stale.

A `test_author` stand-in is a callable taking the bundle and returning a
`TestAuthoringResult`-shaped mapping or object: `model`, `seed`,
`prompt_version`, `cache_hit`, `model_call_error` (`None` or a dict with
`category` and `message`) and `file` (`None` or a dict with `path` and
`content`). `verify` reads `model_call_error` and `file["content"]`;
`file["path"]` is ignored. It writes that content under the glossary's
"Criterion test filename" into a temporary directory, probes it and
runs it there, never writing under `verification/`, so a stale or
probe-failed cached file stays on disk. A stand-in records its calls by
appending to a file the test controls.

A `generated-test` criterion's file runs as
`<interpreter> -m pytest <file>`, `<interpreter>` the one the `python`
adapter's `provision` reported (`D344`), with the working directory
`repo_root` and `PYTHONPATH` set to `gen/<slug>/` (`R-VERIFY-001`). Its
`result` is `pass` exactly when that run exits `0`, and `fail`
otherwise. The mutation score and interface drift change only the
overall verdict, never a criterion's `result`. A fixture plants
`gen/<slug>/<module>.py`, which may be empty when its tests import
nothing from it.

In `test failed its probe: <error kinds>`, the kinds are the distinct
`kind` values of the last probe report's findings whose `severity` is
`"error"`, in order of first appearance, joined by `", "`. A `test-probe`
stand-in's failing finding therefore carries `"severity": "error"`.

## Assets

**The plugin.** `run-environment` provisions every kind and driver
and writes the plugin that gives each run the `asset_runner` fixture
(`specs/architecture/run-environment.md`, `D383`); a verifier test
reaches it only through `verify`.

**A fake kind.** A test concerning assets plants a kind needing no
program, never `javascript`: `<repo_root>/specs/architecture/asset-kind-fake.md`,
frontmatter then the seven `## ` sections of asset-kinds.md's "The
definition", each with one line of text, and
`<repo_root>/gen/kind-fake/kind_fake.py`, its adapter. The component
declares `assets: [fake:data/table.txt]` in its `component.md`
frontmatter and writes `gen/<slug>/data/table.txt` as the two lines
`a=1` and `b=2`. The adapter defines:

- `KIND = "fake"`; `layout_errors` returns `[]`; `surface` returns
  `{"names": []}`; `guidance()` returns
  `{"generator": "Fake generator text.", "test_author": "Fake test text."}`.
- `provision(repo_root)` returns
  `{"ok": True, "reason": "", "versions": {"fake": "1.0"}, "lockfile_sha256": None}`,
  or, for a test of an unprovisioned environment,
  `{"ok": False, "reason": "fake needs fakeprog >= 2", "versions": {}, "lockfile_sha256": None}`.
- `asset_runner(asset_file)` returns `run(entry, args)`, which reads the
  file when called and returns the integer after `<entry>=` on its line.
- `strength_sites(asset_file)` returns
  `[{"description": "1: a"}, {"description": "2: b"}]`, and
  `apply_site(asset_file, site)` adds 1 to the number on that site's
  line.

When the fixture's Python module has no mutation site, a test asserting `run("a", []) == 1` alone scores exactly `0.5`. A kind
with no adapter, such as `nokind`, is declared without planting
`gen/kind-nokind/`.

## The `python` kind

`verify` provisions the implicit `python` asset (`D344`,
`specs/architecture/asset-kind-python.md`) before every declared one,
with its adapter found by Lookup:
`<repo_root>/gen/kind-python/kind_python.py`, else the tool root's. A
fixture that does not concern the `python` kind plants nothing, so the
tool root's real adapter is used: in a criterion run it is
`Path(verifier_orchestrator.__file__).parents[1] / "kind-python" / "kind_python.py"`,
and in a mutation run the same path reaches it through the sandbox's
symbolic link `gen/kind-python`. With no
`environments/python/requirements.lock` in the fixture, its report has
`ok` true, `interpreter` the running interpreter and `lockfile_sha256`
null; its `versions` (the full Python version and the installed
packages' fingerprint, `D345`) a test never writes out: it loads that
file by path with `importlib.util.spec_from_file_location`, calls its
`provision(repo_root)` and takes `["versions"]`. The `assets` entry is
`{"kind": "python", "path": ".", "definition_sha256": None, "adapter_sha256": <that file's hash>, "versions": <those versions>, "lockfile_sha256": None}`,
`definition_sha256` null because the fixture writes no
`specs/architecture/asset-kind-python.md`.

Every pytest run, criterion, baseline or mutant, uses `<interpreter>`
in place of `sys.executable`. When the `python` report has `ok` false
there is none: every `generated-test` and `compiled` criterion fails
as `R-VERIFY-020` states, and only `llm-judge` criteria, which run no
code, are still judged.

**A fake `python` adapter.** A test concerning the `python` kind plants
`<repo_root>/gen/kind-python/kind_python.py` defining `KIND = "python"`,
`layout_errors` returning `[]`, `surface` returning `{"names": []}`,
`guidance()` returning `{"generator": "", "test_author": ""}`,
`strength_sites` returning `[]`, `apply_site` doing nothing, and one of:

- *failing*: `provision(repo_root)` returns
  `{"ok": False, "reason": "python environment: broken", "versions": {}, "lockfile_sha256": None, "interpreter": None}`;
- *wrapped*: `provision(repo_root)` returns
  `{"ok": True, "reason": "", "versions": {"python": "0.0"}, "lockfile_sha256": None, "interpreter": <wrapper>}`,
  where `<wrapper>` is the absolute path of `<repo_root>/wrapper.sh`,
  which the test writes with mode `0o755` as exactly the three lines
  `#!/bin/sh`, `echo called >> <repo_root>/wrapper.log` and
  `exec <sys.executable> "$@"`, the paths written absolute. Each run
  under it appends one line `called` to `wrapper.log`, so a test can
  count its runs; with one passing `generated-test` criterion and no
  mutation site there are at least two, the criterion's and the
  baseline's.
