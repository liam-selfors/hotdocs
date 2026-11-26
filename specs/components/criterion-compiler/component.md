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

See `D206` and `specs/architecture/pipeline-decomposition.md`.

## Scope

**In scope:** parsing the fixed Given/When/Then step grammar
(`specs/architecture/step-phrase-grammar.md`); resolving step references
against a component's `interface/` contract; emitting deterministic test
code under `verification/<component>/compiled/`; failing loudly and
specifically on any step that doesn't parse or doesn't resolve.

**Out of scope:** `generated-test` and `llm-judge` criteria (handled
elsewhere); anything requiring natural-language understanding — the step
grammar is small and fixed, not open English.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/` (`CompileReport` schema).

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

`D43`, `D44`, `D59`, `D62`, `D83`, `D206`, `D214`, `D217`, `D219`, `D226`.
