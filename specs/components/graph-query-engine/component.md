---
id: comp-graph-query-engine
title: Graph Query Engine
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT]
sealed: false
---

# Graph Query Engine

## Purpose

Defines and generates the eight shared DuckDB views
(`specs/architecture/graph-query-engine.md`'s "Query surface") every
adopting component queries instead of writing its own frontmatter
parsing, file globbing, or text extraction.

## Rationale

See `D13`.

## Scope

**In scope:** the eight views' exact `CREATE VIEW` SQL; the loader
contract a consumer calls to create them against a given repo root.

**Out of scope:** deciding which queries a consumer runs against these
views once loaded (that's each consumer's own requirement, e.g.
`spec-linter`'s `R-LINT-020`/`021`); the `yaml`/`duckpgq` extension
choice itself (`specs/architecture/graph-query-engine.md`'s own
decision, unchanged here).

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

`D13`, `D135`, `D176`.
