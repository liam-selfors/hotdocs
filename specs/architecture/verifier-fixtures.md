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
