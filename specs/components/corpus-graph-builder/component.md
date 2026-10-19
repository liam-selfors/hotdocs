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

Builds `verification/corpus-graph.json` (D8/D9) — the single generated
manifest that both D8's traceability matrix and D9's graph/docs explorer
are views over. Walks `P-id → component → R-id → acceptance →
verification-status` and computes corpus-health aggregates.

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

All eight criteria are `kind: compiled` — graph-walking and aggregation
over already-computed data. An eighth component in this corpus with a
fully `compiled` acceptance set.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
