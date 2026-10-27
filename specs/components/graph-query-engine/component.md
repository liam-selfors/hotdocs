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

Defines and generates the seven shared DuckDB views
(`specs/architecture/graph-query-engine.md`'s "Query surface") every
adopting component queries instead of writing its own frontmatter
parsing, file globbing, or text extraction.

## Rationale

Extracted from `specs/architecture/graph-query-engine.md`'s own prose
(`D44`) once that document's embedded SQL stopped being documentation
and started being the actual, unverified implementation — a spec
describing `CREATE VIEW` statements that had never been run (`D43`
found three of the six broken) is exactly the "spec says X, code does
Y" gap `SPEC_GUIDELINES.md` §10 now warns against. This component
makes the SQL a real, generated asset instead: `specs/architecture/
graph-query-engine.md` keeps the *why* (extension choice, adoption
history); this component owns the *what* (each view's exact
definition) and generates the SQL that runs it.

## Scope

**In scope:** the seven views' exact `CREATE VIEW` SQL; the loader
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

All eight criteria are `kind: compiled` — each view's SQL and the
loader's own behavior are fully deterministic, no model or judgment
involved.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft (`D44`), extracted from
  `specs/architecture/graph-query-engine.md`.
