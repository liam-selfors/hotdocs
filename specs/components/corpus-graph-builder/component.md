---
id: comp-corpus-graph-builder
title: Corpus Graph Builder
status: draft
owners: [pipeline-team]
depends_on: [comp-graph-query-engine, comp-spec-linter, comp-provenance-writer, comp-verifier-orchestrator]
realizes: [P-AMBIGUITY-GATE]
sealed: false
---

# Corpus Graph Builder

## Purpose

Builds `verification/corpus-graph.json` — the single generated manifest
the corpus's traceability matrix and graph/docs explorer are both views
over. Walks `P-id → component → R-id → acceptance → verification-status`
and computes corpus-health aggregates.

## Rationale

The traceability-matrix need and the graph/docs explorer this manifest
also feeds were both established early on — this component is the
single source both read from, never two independently-computed copies.

## Scope

**In scope:** building the node/edge graph (products, components, vars);
attaching per-node status (verification, provenance, size-vs-caps,
sealed/override); computing orphan-capability, orphan-component, and
orphan-var rates as aggregate fields; the `hotdocs corpus-graph build`
command.

**Out of scope:** deciding when to rebuild (CI runs the command on
every merge to `main`); rendering anything visual (`docs-site-renderer`'s job);
computing verification or provenance itself (consumes what
`verifier-orchestrator`/`provenance-writer` already produced).

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

All ten are generated tests over small synthetic corpora, run against
the real `graph-query-engine`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
- `D29`: "cache hit" renamed "provenance hit" (`R-GRAPH-008`,
  `constraints.md`), following the corpus-wide rename.
- `depends_on` gained `comp-graph-query-engine` (R-GRAPH-009
  already required building from its views; the dependency was never
  declared — same drift `D13` found and fixed for `spec-linter`). First
  real `gen/corpus-graph-builder/` implementation, produced by a real
  generation step rather than hand-written.
- `D200`: acceptance criteria made concrete; nodes and provenance read
  as the manifest's own JSON; `graph-query-engine` loaded by path
  (`R-GRAPH-010`, `D199`); `R-GRAPH-007` now the CLI, the CI cadence
  moved to scope.
