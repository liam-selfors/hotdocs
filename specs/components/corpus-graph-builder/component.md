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

The single source the traceability matrix and docs explorer both read.

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

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

`D29`, `D13`, `D200`, `D199`.
