---
id: comp-merge-orchestrator
title: Merge Orchestrator
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter, comp-impact-analyzer, comp-component-gate-runner, comp-test-author, comp-capability-scenario-verifier, comp-review-packet-builder, comp-corpus-graph-builder, comp-merge-tracker, comp-llm-endpoint]
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

Originally flagged by `specs/architecture/pipeline-decomposition.md` as
having a 15-component fan-out past the original brainstorm's warn
threshold alongside crowding `component_doc_words` — the same signal
`D14` had already resolved once by extracting
`capability-scenario-verifier`. `D76` applied the same fix a second
time, extracting `component-gate-runner`: fan-out dropped to 9 as a
result, because every dependency it encapsulates was previously used
for nothing but that one gauntlet.

## Scope

**In scope:** sequencing calls to `component-gate-runner` across the
blast radius, in `depends_on` order (R-MERGE-023), running every
impacted component to completion before evaluating block status
(R-MERGE-017, no fail-fast) so a blocked merge's re-run is a complete,
free recovery path (R-MERGE-018); passing each component's own
caller-supplied `retry_feedback` through to its `component-gate-runner`
call (R-MERGE-022); writing a per-attempt record (R-MERGE-021) via
`merge-tracker` after each `component-gate-runner` call concludes;
calling `capability-scenario-verifier` once every component has passed
verification (R-MERGE-014 owns *when*/*with what*, not the dispatch
mechanics, R-SCENARIO-001); wiring the real `test_author`/`judge`
closures (backed by `test-author`/`llm-endpoint`) and passing them into
both every `component-gate-runner` call and the
`capability-scenario-verifier` call — the one wiring site for both
(`D76`).

**Out of scope:** any gate's own logic; the per-component
provenance/generation/verification/scan/provenance-write gauntlet
itself (`component-gate-runner`, `D76`).

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

All fifteen criteria are `kind: compiled` — tested by mocking every
dependency and asserting on call order/arguments, the same pattern
`verifier-orchestrator` already established for coordination logic.

## Non-functional constraints

See `constraints.md`.

## Open questions

- ~~Exact value of `k`~~ — `D3` resolved this (default `k=2`,
  diagnostic-guided retry, later retired along with the whole best-of-k
  mechanism this question was about), superseding the answer along with
  the question.
- ~~Whether `component-gate-runner`'s parallelization (`R-GATE-005`) is
  literal concurrency or just "no artificial sequential dependency"~~ —
  resolved by `specs/decisions/D8.md` (the requirement constrains the
  *outcome*, not the mechanism — `R-MERGE-017`).
- ~~Whether a sealed component's path (`R-GATE-007`) still participates
  in the provenance-check short-circuit (`R-GATE-001`)~~ — resolved
  (`D8`, mechanism updated by `D29`): it never does, unconditionally.
  See `R-GATE-007`.

## Change log

- Initial draft.
- `D8`: resolved the sealed-component cache-hit question (originally
  `R-MERGE-015`, now `R-GATE-007`) and `D25` added
  `tracking_write_error` visibility for a failed `merge-tracker` call
  (`R-MERGE-019`, `AC-MERGE-024`).
- `D29`: the provenance check (originally `R-MERGE-003`, now
  `R-GATE-001`) checks `provenance-checker`, not `cache-manager`;
  `depends_on` swapped accordingly at the time. `cache_hit` renamed
  `provenance_hit`.
- `D37`: `R-MERGE-023` — generation now sequenced in `depends_on` order
  within a blast radius, for `dependency_usage` (`R-ASSEMBLE-011`).
- `D76`: extracted `component-gate-runner` (the per-component
  provenance/generation/verification/scan/provenance-write gauntlet,
  originally `R-MERGE-003/004/005/006/008/009/015`) once fan-out and
  `component_doc_words` crowded together a second time — the same
  signal `D14` resolved once before. `depends_on` dropped from 15 to 9;
  `MergeResult.components` entries are now `ComponentPipelineResult`,
  owned by the new component.
