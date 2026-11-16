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
the stand-ins `verify` runs against.

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
so a test does not lint its fixture (`R-AUTHOR-015`).

A `test-probe` stand-in defines `probe(test_source, criterion_bundle,
module_name, *, timeout=60.0)` returning an object with `ok` (bool),
`findings` (a list of dicts with `kind`, `severity`, `line` and
`message`) and `to_dict()`. A fixture that does not concern probing
plants one returning `ok` true with no findings, so every test runs.

A `spec-bundle-assembler` stand-in defines
`assemble_criterion(component_id, criterion_id, repo_root)`, the only
assembler function `verify` calls. Its return value, a `CriterionBundle`
or a mapping with its keys, is the bundle `verify` hashes for
`R-VERIFY-019`, passes to `test_author` and passes to `test-probe`'s
`probe`. A test that needs a cached file's correct header plants such a
stand-in with known `criterion_text` and `requirement_text` and writes
the first line as `# hotdocs-criterion: sha256:` followed by
`hashlib.sha256((criterion_text + "\n" + requirement_text).encode("utf-8")).hexdigest()`.
A header line is one matching
`^# hotdocs-criterion: sha256:[0-9a-f]{64}$`; any other first line,
including uppercase hex, is no header, so that file is never stale.

From a `test_author` outcome (`test-author`'s `TestAuthoringResult`, as
a mapping or an object) `verify` reads `model_call_error` and
`file["content"]` only; `file["path"]` is ignored. It writes that content
under the glossary's "Criterion test filename" into a temporary
directory, probes it and runs it there. It never writes under
`verification/`, so a stale or probe-failed cached file stays on disk.

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
