---
id: comp-merge-orchestrator
title: Merge Orchestrator
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter, comp-impact-analyzer, comp-spec-bundle-assembler, comp-generator, comp-test-author, comp-capability-scenario-verifier, comp-verifier-orchestrator, comp-license-scanner, comp-secret-scanner, comp-provenance-checker, comp-provenance-writer, comp-review-packet-builder, comp-corpus-graph-builder, comp-merge-tracker, comp-llm-endpoint]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE, P-COMPLIANCE-GATE, P-MERGE-VISIBILITY]
sealed: false
---

# Merge Orchestrator

## Purpose

Sequences every other component into one merge, per `SPEC_GUIDELINES.md`
§6: lint, impact analysis, generation, verification, compliance gates,
capability-scenario verification, provenance, review packet, atomic
commit.

## Rationale

Flagged by `specs/architecture/pipeline-decomposition.md` as having a
15-component fan-out past the original brainstorm's warn threshold — a
known, accepted tension, not something to resolve by artificially
shrinking this list.

## Scope

**In scope:** sequencing and parallelizing calls to every other
component, in `depends_on` order (R-MERGE-023); calling `generator`
exactly once per cache-miss component per merge attempt (R-MERGE-005,
no retry decision to own — one call, immediate block on failure),
optionally carrying caller-supplied `retry_feedback` (R-MERGE-022,
passed through, never computed here); writing a per-attempt record
(R-MERGE-021) via `merge-tracker` after that call and the verification
call conclude; calling `capability-scenario-verifier` once every
component has passed verification (R-MERGE-014 owns *when*/*with
what*, not the dispatch mechanics, R-SCENARIO-001); wiring the real
`test_author`/`judge` closures (backed by `test-author`/`llm-endpoint`,
R-MERGE-004) into both that call and `verifier-orchestrator`'s; routing
a sealed component away from generation (R-MERGE-015); running every
impacted component to completion before evaluating block status
(R-MERGE-017, no fail-fast) so a blocked merge's re-run is a complete,
free recovery path (R-MERGE-018).

**Out of scope:** any gate's own logic.

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

All twenty-five criteria are `kind: compiled` — tested by mocking every
dependency and asserting on call order/arguments, the same pattern
`verifier-orchestrator` already established for coordination logic.

## Non-functional constraints

See `constraints.md`.

## Open questions

- ~~Exact value of `k`~~ — `D3` resolved this (default `k=2`,
  diagnostic-guided retry, later retired along with the whole best-of-k
  mechanism this question was about), superseding the answer along with
  the question.
- ~~Whether R-MERGE-008's parallelization is literal concurrency or just
  "no artificial sequential dependency"~~ — resolved by
  `specs/decisions/D8.md` (the requirement constrains the *outcome*,
  not the mechanism — `R-MERGE-017`).
- ~~Whether R-MERGE-015's sealed-component path still participates in
  R-MERGE-003's short-circuit~~ — resolved (`D8`, mechanism updated by
  `D29`): it never does, unconditionally. See `R-MERGE-015`.

## Change log

- Initial draft.
- `D8`: resolved the sealed-component cache-hit question
  (`R-MERGE-015`) and `D25` added `tracking_write_error` visibility for
  a failed `merge-tracker` call (`R-MERGE-019`, `AC-MERGE-024`).
- `D29`: `R-MERGE-003` now checks `provenance-checker`, not
  `cache-manager`; `depends_on` swaps accordingly. `cache_hit` renamed
  `provenance_hit`.
- `D37`: `R-MERGE-023` — generation now sequenced in `depends_on` order
  within a blast radius, for `dependency_usage` (`R-ASSEMBLE-011`).
