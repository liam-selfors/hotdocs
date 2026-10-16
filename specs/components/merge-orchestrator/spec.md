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

- **R-MERGE-001** — MUST run `spec-linter` first, before any other
  component; a hard-fail finding MUST block the merge immediately — the
  cheapest gate runs first and fails fast.
- **R-MERGE-002** — MUST run `impact-analyzer` to compute the blast radius
  from the changed spec ids.
- **R-MERGE-003** — For each impacted component, MUST check `cache-manager`
  for a cache hit on the full spec bundle before doing anything else; a hit
  MUST short-circuit straight to restoring the matching prior artifacts
  (D11), skipping R-MERGE-004 through R-MERGE-008 for that component
  entirely — not running them and discarding the result, actually skipping
  them.
- **R-MERGE-004** — For a cache miss, MUST call `spec-bundle-assembler`
  then `generator` (cold mode, sample index 0) to produce a candidate, then
  `verifier-orchestrator` to check it — **wiring a real `test_author`
  callable (backed by `test-author`) and a real `judge` callable (a direct
  call to the configured model, for `llm-judge`-kind criteria) into that
  call.** This component is where those two injectable parameters actually
  get their real implementations in production; nothing upstream of this
  requirement assigned who does that wiring, so it's stated explicitly here
  rather than left implicit.
- **R-MERGE-005** — **This is the best-of-k retry loop (D3), owned here.**
  If `verifier-orchestrator`'s verdict is `fail`, MUST call `generator`
  again with a new sample index, up to a configured `k` (default range
  2–4) total attempts, re-verifying each. The first sample whose verdict is
  `pass` MUST be kept; its sample index MUST be the one recorded for
  provenance (D3).
- **R-MERGE-006** — If all `k` samples fail verification, the merge MUST be
  blocked for that component — retries exhausted, not silently accepted.
- **R-MERGE-007** — MUST invoke `cross-model-divergence-checker` for each
  impacted component for which `cross_model_divergence_check` or
  `fallback_standby_build` resolves to `enabled` with a second model
  configured — and MUST NOT invoke it otherwise (R-XMODEL-001's
  precondition is enforced by never calling it, not by calling it and
  discarding the "not applicable" result).
- **R-MERGE-008** — MUST invoke `license-scanner` and `secret-scanner`
  unconditionally for every impacted component — never toggle-gated
  (D7/D12). R-MERGE-007 and R-MERGE-008, together with R-MERGE-004's
  generation call, MAY run in parallel with each other per component (D13)
  — they have no sequential dependency on each other given the same
  inputs.
- **R-MERGE-009** — Once generation/verification, the cross-model check
  (if it ran), and both scans have produced their results for a component,
  MUST invoke `provenance-writer` for that component.
- **R-MERGE-010** — Once `provenance-writer` has completed for every
  impacted component in this merge, MUST invoke `corpus-graph-builder` and
  `review-packet-builder`.
- **R-MERGE-011** — The overall merge MUST be blocked if any impacted
  component exhausted retries (R-MERGE-006), or `cross-model-divergence-
  checker` reported a blocking divergence, or either scanner reported a
  blocking flag — and MUST proceed otherwise.
- **R-MERGE-012** — On success, MUST commit `specs/`, `gen/`, and
  `verification/` (including `corpus-graph.json`) atomically, in one
  squashed commit (`SPEC_GUIDELINES.md` §6 step 8 / D6).
- **R-MERGE-013** — The review packet MUST be presented for human review as
  part of the merge; the generated code itself MUST NOT be presented as the
  primary review artifact (principle 6, enforced structurally here by what
  this component surfaces, not left to reviewer discipline alone).

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`MergeResult` schema).

## Acceptance criteria

See `acceptance.md`.

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
