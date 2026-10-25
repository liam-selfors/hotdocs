---
id: comp-merge-orchestrator
title: Merge Orchestrator
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter, comp-impact-analyzer, comp-spec-bundle-assembler, comp-generator, comp-test-author, comp-criterion-compiler, comp-verifier-orchestrator, comp-license-scanner, comp-secret-scanner, comp-cache-manager, comp-provenance-writer, comp-review-packet-builder, comp-corpus-graph-builder]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE, P-COMPLIANCE-GATE]
sealed: false
---

# Merge Orchestrator

## Purpose

Sequences every other component into one merge, per `SPEC_GUIDELINES.md`
§6: lint, impact analysis, generation (with retry), verification,
compliance gates, golden-scenario verification, provenance, review packet,
atomic commit. This is the component
`specs/architecture/pipeline-decomposition.md` flagged as having a
13-component fan-out past D2's warn threshold — a known, accepted tension
(see that document), not something to resolve by artificially shrinking
this list.

## Scope

**In scope:** sequencing and parallelizing calls to every other component;
owning the best-of-k retry loop (D3) — this is the component that resolves
the gap `generator`'s spec surfaced: nothing before this assigned who
retries generation on a verification failure, and the answer is here, not
inside `generator` itself. The retry loop is diagnostic-guided
(R-MERGE-005): each retry's `retry_feedback` is this component's own
extraction of the failing `R-id`s from the immediately preceding attempt's
`requirement_results` (R-VERIFY-011) — `merge-orchestrator` reads that
field and passes it through, it does not compute pass/fail itself. `k`
itself defaults to 2 and is overridable per-component (R-MERGE-016).
Since D16: also owns running golden-scenario
verification against the real assembled system (R-MERGE-014), reusing the
exact same `criterion-compiler`/`test_author`/`judge` dispatch already
wired for `verifier-orchestrator` — not a second dispatch mechanism. Also
owns routing a sealed component away from generation entirely (R-MERGE-015)
— the primary layer of the sealed/pinned-override write-protection
invariant, previously only asserted as something this component "should"
do in `generator`'s own spec, never specified here until now. Also owns
running every impacted component to completion before evaluating block
status (R-MERGE-017) — no fail-fast short-circuiting — which is what
makes re-running a blocked merge a complete, free recovery path
(R-MERGE-018): nothing dedicated to "retry," just the same cache-hit/
cache-miss behavior every merge already has, now relied upon explicitly
for partial-failure recovery, not only for genuinely unchanged specs.

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

All twenty criteria are `kind: compiled` — tested by mocking every
dependency and asserting on call order/arguments, the same pattern
`verifier-orchestrator` already established for coordination logic. An
eleventh component in this corpus
whose entire acceptance set is `compiled` — the capstone data point for
D5's guidance: even the component that sequences every model-calling,
judgment-involving gate in the whole pipeline is, in its own right, fully
deterministic.

## Non-functional constraints

See `constraints.md`.

## Open questions

- ~~Exact value of `k` (best-of-k sample count) — D3 names a range (2–4),
  not a fixed default~~ — resolved: default `k=2`, per-component override
  via `best_of_k` frontmatter (R-MERGE-016), alongside diagnostic-guided
  retry feeding each retry the immediately preceding attempt's failing
  `R-id`s (R-MERGE-005, R-GEN-010, R-VERIFY-011).
- ~~Whether R-MERGE-008's parallelization (with R-MERGE-004) is literal
  concurrent execution or just "no artificial sequential dependency" at
  the spec level~~ — resolved without forcing an answer: R-MERGE-017
  constrains the *outcome* (every impacted component attempted to
  completion, no fail-fast short-circuiting) rather than the mechanism —
  sequential and concurrent execution both satisfy it. What actually
  mattered about this question was ruling out fail-fast, not settling on
  a concurrency primitive.
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
