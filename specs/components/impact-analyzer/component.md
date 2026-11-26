---
id: comp-impact-analyzer
title: Impact Analyzer
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter]
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Impact Analyzer

## Purpose

From a set of changed spec ids, computes the minimal **blast radius**
— the set of components
that actually need regeneration or re-verification for this change.
Runs after `spec-linter` passes, assuming a validated, acyclic,
reference-resolved corpus graph; it does not re-validate that graph
itself.

## Rationale

See `specs/architecture/graph-query-engine.md` (`R-IMPACT-009`).

## Scope

**In scope:** determining, for a given set of changed spec ids, which
components are directly changed and which are transitively impacted because
something they depend on changed in a way that affects their contract.
Distinguishing a dependency's *contract* changing from its *internals*
changing, so an unrelated component's change doesn't force regeneration of
everything downstream of it. Per `D2`: distinguishing, within the
contract itself, type-level content (`cli.md`/`library.md`/`data/*.md` —
always coarse, always propagates) from behavioral guarantees
(`guarantees/*.md` — narrowable, opt-in, per `depends_on_guarantees`).

**Out of scope:** generation itself; deciding *how* to regenerate a component,
only *whether* it's in scope this merge; re-running `spec-linter`'s own
checks.

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

`D48`, `D49`, `D50`, `D329`, `D347`.
