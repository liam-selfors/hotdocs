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

- **R-GRAPH-001** — The graph MUST contain one node per product capability
  (`P-id`), one per component, and one per `specs/vars/` declaration in the
  corpus.
- **R-GRAPH-002** — The graph MUST contain one edge per `depends_on`,
  `realizes`, and `uses_var` relationship declared anywhere in the corpus.
- **R-GRAPH-003** — Each component node MUST carry its current verification
  status (`verifier-orchestrator`'s latest `VerificationReport`), provenance
  summary (`provenance-writer`'s manifest), size-vs-D2-caps status, and
  `sealed`/pinned-override status — everything D9's per-node detail view
  needs, assembled once here rather than separately by the renderer.
- **R-GRAPH-004** — The graph MUST include corpus-wide aggregate fields for
  orphan-capability rate and orphan-component rate (D8) — the actual
  computed values, not merely per-node flags a consumer would have to
  re-derive the rate from.
- **R-GRAPH-005** — The graph MUST similarly include the orphan-var rate
  (D12) as a computed aggregate field.
- **R-GRAPH-006** — The output file MUST be exactly
  `verification/corpus-graph.json` — the one artifact D8's traceability
  matrix and D9's docs-site-renderer both consume, never a second,
  duplicate manifest.
- **R-GRAPH-007** — This component MUST run on every merge to `main` (D9's
  build-cadence decision) — never a scheduled or periodic job.
- **R-GRAPH-008** — The graph MUST be a deterministic function of corpus +
  provenance + verification state: the same inputs always produce the same
  graph, byte for byte — required because this file is committed under D6
  and participates in cache-hit comparisons the same way any other gate
  output does.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`CorpusGraph` schema).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
