---
id: comp-merge-orchestrator
title: Merge Orchestrator
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter, comp-impact-analyzer, comp-spec-bundle-assembler, comp-generator, comp-test-author, comp-golden-scenario-verifier, comp-verifier-orchestrator, comp-license-scanner, comp-secret-scanner, comp-cache-manager, comp-provenance-writer, comp-review-packet-builder, comp-corpus-graph-builder, comp-merge-tracker, comp-llm-endpoint]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE, P-COMPLIANCE-GATE, P-MERGE-VISIBILITY]
sealed: false
---

# Merge Orchestrator

## Purpose

Sequences every other component into one merge, per `SPEC_GUIDELINES.md`
§6: lint, impact analysis, generation, verification, compliance gates,
golden-scenario verification, provenance, review packet, atomic commit.

## Rationale

Flagged by `specs/architecture/pipeline-decomposition.md` as having a
15-component fan-out past D2's warn threshold — a known, accepted
tension (see that document), not something to resolve by artificially
shrinking this list.

## Scope

**In scope:** sequencing and parallelizing calls to every other
component; calling `generator` exactly once per cache-miss component per
merge attempt (R-MERGE-005) — since `D31` retired the best-of-k retry
loop that used to call it again on failure, there is no retry *decision*
left to own here, only the one call and an immediate block on failure.
That one call MAY carry caller-supplied `retry_feedback` (`R-MERGE-022`,
`D33`) — this component passes it through for exactly the components
named, never computes or decides on it itself. Since `D32`, also writes
a per-attempt record (`R-MERGE-021`) via
`merge-tracker` right after that call (and the verification call, if
reached) concludes, so a human has full diagnostic detail before
deciding whether to just re-run or fix the spec first. Since D16: also
calls `golden-scenario-verifier` once every component has passed
per-component verification (R-MERGE-014) — the dispatch itself moved
there (D25), this component only owns *when* and *with what* it's
called. Since D30, the real `test_author`/`judge` callables wired into
both that call and `verifier-orchestrator`'s (R-MERGE-004) are backed by
`llm-endpoint`. Also routes a sealed component away from generation
entirely (R-MERGE-015), and runs every impacted component to
completion before evaluating block status (R-MERGE-017) — no fail-fast —
which is what makes re-running a blocked merge a complete, free recovery
path (R-MERGE-018).

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

All twenty-two criteria are `kind: compiled` — tested by mocking every
dependency and asserting on call order/arguments, the same pattern
`verifier-orchestrator` already established for coordination logic.

## Non-functional constraints

See `constraints.md`.

## Open questions

- ~~Exact value of `k`~~ — `D17` resolved this (default `k=2`,
  diagnostic-guided retry); `D31` later retired the whole best-of-k
  mechanism this question was about, superseding the answer along with
  the question.
- ~~Whether R-MERGE-008's parallelization is literal concurrency or just
  "no artificial sequential dependency"~~ — resolved by
  `specs/decisions/D21.md` (the requirement constrains the *outcome*,
  not the mechanism — `R-MERGE-017`).
- Whether R-MERGE-015's sealed-component path still participates in
  R-MERGE-003's cache-hit short-circuit, and if so, what a "cache hit"
  even means for a component whose code is hand-maintained rather than
  regenerated (the spec bundle hash could match a prior verified commit,
  but nothing about regeneration risk — the usual reason freshness
  matters — applies the same way to code a human controls directly). Not
  addressed here; R-MERGE-015 as written applies R-MERGE-003's existing
  precondition ("for a cache miss") without re-examining whether that
  precondition means the same thing for a sealed component.

## Change log

- Initial draft.
