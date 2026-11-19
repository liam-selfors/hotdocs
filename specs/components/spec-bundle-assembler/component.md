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
alongside its `interface/` content (`R-ASSEMBLE-010`), so a generating
model sees not just a dependency's contract but what it's for.

## Rationale

The cold-vs-hint split traces to the original brainstorm.

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

Every criterion is `kind: generated-test`, over the synthetic corpus
`testing.md` defines.

## Non-functional constraints

See `constraints.md`.

## Open questions

- ~~Hash raw bytes or a normalized form?~~ Resolved: raw bytes.
  Markdown whitespace can be meaningful, so no normalization is safe;
  `R-LINT-019` rejects trailing whitespace instead.

## Change log

Each decision holds its full rationale.

- Initial draft; first implementation hand-written, `depends_on` gains
  `comp-graph-query-engine`.
- `D37`: `dependency_usage` (`R-ASSEMBLE-011`). `D60`: a sealed
  dependency's card reads its `source_path`.
- `D69`: the target's own Rationale, Open questions and Change log are
  excluded (`R-ASSEMBLE-001`).
- `D100`: `CriterionBundle.dependency_interfaces`. `D101`: corpus
  structure comes only from `spec-linter` (`R-ASSEMBLE-012`).
- `D109`, `D118`: cold-generated; the hand-written suite retired.
  `D114`: one level of transitive types (`R-ASSEMBLE-013`).
- `D177`: `AC-ASSEMBLE-011`'s failure traced to its test's fixture.
- `D207`: the synthetic corpus every criterion uses is stated once, in
  the library interface.
