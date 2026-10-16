---
id: comp-merge-orchestrator
title: Merge Orchestrator
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter, comp-impact-analyzer, comp-spec-bundle-assembler, comp-generator, comp-test-author, comp-verifier-orchestrator, comp-cross-model-divergence-checker, comp-license-scanner, comp-secret-scanner, comp-cache-manager, comp-provenance-writer, comp-review-packet-builder, comp-corpus-graph-builder]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE, P-COMPLIANCE-GATE]
sealed: false
---

# Merge Orchestrator

## Purpose

Sequences every other component into one merge, per `SPEC_GUIDELINES.md`
§6: lint, impact analysis, generation (with retry), verification,
cross-model/compliance gates, provenance, review packet, atomic commit.
This is the component `specs/architecture/pipeline-decomposition.md`
flagged as having an 11-component fan-out past D2's warn threshold — a
known, accepted tension (see that document), not something to resolve by
artificially shrinking this list.

## Scope

**In scope:** sequencing and parallelizing calls to every other component;
owning the best-of-k retry loop (D3) — this is the component that resolves
the gap `generator`'s spec surfaced: nothing before this assigned who
retries generation on a verification failure, and the answer is here, not
inside `generator` itself.

**Out of scope:** any gate's own logic — this component calls, it doesn't
reimplement.

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

All thirteen criteria are `kind: compiled` — tested by mocking every
dependency and asserting on call order/arguments, the same pattern
`verifier-orchestrator` and `cross-model-divergence-checker` already
established for coordination logic. A twelfth component in this corpus
whose entire acceptance set is `compiled` — the capstone data point for
D5's guidance: even the component that sequences every model-calling,
judgment-involving gate in the whole pipeline is, in its own right, fully
deterministic.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Exact value of `k` (best-of-k sample count) — D3 names a range (2–4), not
  a fixed default. Left as a `pipeline/`-level configuration value, not
  hardcoded in this spec.
- Whether R-MERGE-007/008's parallelization is literal concurrent
  execution or just "no artificial sequential dependency" at the spec
  level (leaving scheduling to the implementation) — this spec states the
  *independence*, not a specific concurrency mechanism.

## Change log

- Initial draft.
