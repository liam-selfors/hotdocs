---
id: comp-corpus-graph-builder
title: Corpus Graph Builder
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter, comp-provenance-writer, comp-verifier-orchestrator]
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

D8 established the traceability-matrix need; D9 established the
graph/docs explorer this manifest also feeds — this component is the
single source both read from, never two independently-computed copies.

## Scope

**In scope:** building the node/edge graph (products, components, vars);
attaching per-node status (verification, provenance, size-vs-caps,
sealed/override); computing orphan-capability, orphan-component, and
orphan-var rates as aggregate fields.

**Out of scope:** rendering anything visual (`docs-site-renderer`'s job);
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

All nine criteria are `kind: compiled` — graph-walking and aggregation
over already-computed data; nothing here needs a model or judgment.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
- `D39`: "cache hit" renamed "provenance hit" (`R-GRAPH-008`,
  `constraints.md`), following the corpus-wide rename.
