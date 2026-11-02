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
(`D13`) once that document's embedded SQL stopped being documentation
and started being the actual, unverified implementation — a spec
describing `CREATE VIEW` statements that had never been run is
exactly the "spec says X, code does Y" gap `SPEC_GUIDELINES.md` §10
now warns against. This component
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

All nine criteria are `kind: compiled` — each view's SQL and the
loader's own behavior are fully deterministic, no model or judgment
involved.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft (`D13`), extracted from
  `specs/architecture/graph-query-engine.md`.
- `D135`: `interface/library.md` states the literal yaml extension
  install incantation (`INSTALL yaml FROM community`, never a bare
  `INSTALL yaml`) — found once a fresh caller (`decision-drift-
  detector`) hit a real registry conflict that prose alone ("the
  `yaml` community extension") didn't prevent.
- `D176`: `views.sql` brought up to `R-GQE-001`/`002`/`008` — the `decision`
  node kind, the `supersedes`/`builds_on` edges, and `decision_lineage`
  had never been implemented. Decision fields are read from the
  frontmatter block only (a decision's prose quoted `supersedes:`).
