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
the stand-ins `verify` runs against, and how a test run reaches a
declared asset (`specs/architecture/asset-kinds.md`, `D343`).

## Rules

A test plants a fake dependency at the path `verify` loads it from:
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
root holds only `gen/` and `specs/asset-kinds/`
(`specs/architecture/mutation-runs.md`), while a
sibling `gen/` directory resolves to the tree the criterion run used.

A `spec-bundle-assembler` stand-in defines
`assemble_criterion(component_id, criterion_id, repo_root)`, the only
assembler function `verify` calls. Its return value, a `CriterionBundle`
or a mapping with its keys, is the bundle `verify` hashes for
`R-VERIFY-019`, passes to `test_author` and passes to `test-probe`'s
`probe`. A test that needs a cached file's correct header plants such a
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
`<sys.executable> -m pytest <file>` with the working directory
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

**The `asset_runner` plugin.** Each `verify` call writes a fresh
temporary directory `<plug>` holding only `hotdocs_asset_runner.py`.
Every pytest run of a criterion, baseline or mutant gets
`-p hotdocs_asset_runner`, `<plug>` as the last `PYTHONPATH` entry, and
the environment variable `HOTDOCS_ASSETS`: a JSON list with one object
per declared asset, in declaration order,
`{"path": <declared path>, "file": <absolute path of that asset in the code being verified>, "adapter": <absolute path of the adapter module found by Lookup>}`,
and `[]` when the component declares none. The code being verified is
`gen/<slug>/` for a criterion run and `<tmp>/gen/<slug>/` for a
mutation run. The plugin defines the function-scoped fixture
`asset_runner`, a function of one `path`: for the entry whose `path`
equals it, it loads the module at `adapter` with
`importlib.util.spec_from_file_location` and returns
`module.asset_runner(Path(file))`; any other `path` raises
`KeyError(path)`. It reads `HOTDOCS_ASSETS` when the fixture is
requested, and imports nothing from `hotdocs`.

**A fake kind.** A test concerning assets plants a kind needing no
program, never `javascript`: `<repo_root>/specs/asset-kinds/fake.md`,
frontmatter then the seven `## ` sections of asset-kinds.md's "The
definition", each with one line of text, and
`<repo_root>/gen/kind-fake/kind_fake.py`, its adapter. The component
declares `assets: [fake:data/table.txt]` in its `component.md`
frontmatter and writes `gen/<slug>/data/table.txt` as the two lines
`a=1` and `b=2`. The adapter defines:

- `KIND = "fake"`; `layout_errors` returns `[]`; `surface` returns
  `{"names": []}`.
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
