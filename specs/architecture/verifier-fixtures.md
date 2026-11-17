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
`<repo_root>/gen/spec-bundle-assembler/spec_bundle_assembler.py` or
`<repo_root>/pipeline/criterion-compiler/criterion_compiler.py`. A fixture
component under test is never `sealed`, unless its criterion concerns
sealed verification (`R-VERIFY-017`): a sealed one runs only its
characterization tests, never its compiled or generated ones. An
unsealed fixture component lints clean only with `realizes: [P-<ID>]`
naming a capability file the fixture also writes under `specs/product/`
(`R-LINT-006`). Name fixture functions other than `foo`:
`spec-bundle-assembler`'s interface text declares `foo(x)`, which
`test-author`'s fake-arity check (`R-AUTHOR-020`) would match. Every
fixture criterion has at least one Given, one When and one Then step
(`R-LINT-010`). `verify` checks no precondition against `spec-linter`,
so a test does not lint its fixture (`R-AUTHOR-015`).

A `spec-bundle-assembler` stand-in defines
`assemble_criterion(component_id, criterion_id, repo_root)`, the only
assembler function `verify` calls. Its return value, a `CriterionBundle`
or a mapping with its keys, is the bundle `verify` hashes for
`R-VERIFY-019` and passes to `test_author`. A test that needs a cached
file's correct header plants such a stand-in with known
`criterion_text` and `requirement_text` and writes the first line as
`# hotdocs-criterion: sha256:` followed by
`hashlib.sha256((criterion_text + "\n" + requirement_text).encode("utf-8")).hexdigest()`.
A header line is one matching
`^# hotdocs-criterion: sha256:[0-9a-f]{64}$`; any other first line,
including uppercase hex, is no header, so that file is stale.

A `test_author` stand-in is a callable taking the bundle and returning a
`TestAuthoringResult`-shaped mapping or object: `model`, `seed`,
`prompt_version`, `cache_hit`, `model_call_error` (`None` or a dict with
`category` and `message`) and `file` (`None` or a dict with `path` and
`content`). `verify` reads `model_call_error` and `file["content"]`;
`file["path"]` is ignored. It writes that content under the glossary's
"Criterion test filename" into a temporary directory and runs it there,
never writing under `verification/`, so a stale cached file stays on
disk. A stand-in records its calls by appending to a file the test
controls.

A `generated-test` criterion's file runs as
`<sys.executable> -m pytest <file>` with the working directory
`repo_root` and `PYTHONPATH` set to `gen/<slug>/` (`R-VERIFY-001`). Its
`result` is `pass` exactly when that run exits `0`, and `fail`
otherwise. The mutation score and interface drift change only the
overall verdict, never a criterion's `result`. A fixture plants
`gen/<slug>/<module>.py`, which may be empty when its tests import
nothing from it.
