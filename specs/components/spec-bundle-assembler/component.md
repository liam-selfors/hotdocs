---
id: comp-spec-bundle-assembler
title: Spec Bundle Assembler
status: draft
owners: [pipeline-team]
depends_on: [comp-graph-query-engine, comp-spec-linter]
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Spec Bundle Assembler

## Purpose

Assembles a component's full generation input — its own `component.md` +
`requirements/` + `interface/` + `constraints.md`, its dependencies'
`interface/` content and `Purpose` text, its referenced `specs/vars/`
declarations, and `specs/glossary.md` — into one payload (`SpecBundle`).
Reused by canonical generation and hint-mode previews — one assembly
implementation, not two.

## Scope

**In scope:** reading and concatenating the right files for a given
component id; computing `spec_bundle_hash`; the cold-vs-hint distinction
at the bundle level; including each dependency's `Purpose` text
alongside its `interface/` content (`R-ASSEMBLE-010`).

**Out of scope:** calling any model (`generator`'s job); deciding *whether*
to regenerate (`impact-analyzer`'s job); verifying anything.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

`D37`, `D60`, `D69`, `D100`, `D101`, `D109`, `D114`, `D118`, `D177`,
`D207`, `D343`, `D379`.
