---
id: comp-criterion-compiler
title: Criterion Compiler
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
sealed: true
source_path: pipeline/criterion-compiler/
---

# Criterion Compiler

## Purpose

Deterministically compiles `kind: compiled` Given/When/Then acceptance
criteria into executable test scaffolding, with no model involved at any
step. Sealed (`sealed: true`): the pipeline never regenerates or swaps it.

## Rationale

The trust anchor for `compiled`-kind criteria: they are the strongest
tier of evidence because nothing model-driven runs between the criterion
and the check. Its code is generated from this spec like every other
component's, but it is sealed. `generator` refuses it, and a person
installs each version only after it passes its generated tests and the
hand-maintained characterization suite in
`verification/criterion-compiler/`, which is also the only thing
`verifier-orchestrator` runs to verify it (`D206`). The trust rests on
that human-written suite and on the person installing the version, not
on who wrote the code. See `specs/architecture/pipeline-decomposition.md`.

## Scope

**In scope:** parsing the fixed Given/When/Then step grammar
(`specs/architecture/step-phrase-grammar.md`); resolving step references
against a component's `interface/` contract; emitting deterministic test
code under `verification/<component>/compiled/`; failing loudly and
specifically on any step that doesn't parse or doesn't resolve.

**Out of scope:** `generated-test` and `llm-judge` criteria (handled
elsewhere); anything requiring natural-language understanding — the step
grammar is intentionally small and fixed, not open English, precisely so this
component never needs a model call (see Non-functional constraints).

**A circularity this component's own acceptance criteria must resolve:**
none of them can be `kind: compiled`, since using the compiler to verify
the compiler proves nothing about its own bugs. All are
`kind: generated-test`, written by an agent from this spec's prose with no
access to the implementation.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/` (`CompileReport` schema). The step-grammar reference
itself lives at `specs/architecture/step-phrase-grammar.md`, not here — see
Purpose above for why.

## Acceptance criteria

See `acceptance/`. All `kind: generated-test`, not `compiled` (see Scope).
Sealed verification runs the hand-maintained characterization suite
(`verification/criterion-compiler/test_*.py`), which a person writes and
no generated version ever touches.

## Non-functional constraints

See `constraints.md`.

## Open questions

None. The three earlier ones were resolved by `R-COMPILE-011` (one
`pytest` target), the grammar's move to `specs/architecture/`, and
`R-COMPILE-007` (where literal substitution ends).

## Change log

Each decision holds its full rationale.

- Initial draft.
- `D43`: every prose `compiled` criterion reclassified. `D44`: first
  implementation, hand-written. `D59`: `compile_criterion`. `D62`: emitted
  code imports and qualifies the target module. `D83`: dependents load
  this component lazily from `repo_root`.
- `D206`: generated from this spec and installed at `source_path` with
  `--sealed-install`; still sealed, the characterization suite still
  hand-maintained. `D214`: exact grammar forms and located errors.
- `D217`: how the interface surface is read, and substitution's emitted
  form. `D219`: emitted literals. `D226`: `AC-COMPILE-016`.
