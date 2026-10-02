---
id: comp-cross-model-divergence-checker
title: Cross-Model Divergence Checker
status: draft
owners: [pipeline-team]
depends_on: [comp-generator, comp-verifier-orchestrator, comp-cache-manager]
realizes: [P-AMBIGUITY-GATE]
cross_model_divergence_check: enabled
sealed: false
---

# Cross-Model Divergence Checker

## Purpose

Implements D3's toggleable gate and D10's standby-build mechanism with one
component: regenerates a component with a second model and either (a)
differential-tests it against the canonical build to catch underspecified
acceptance criteria before merge, or (b) just keeps it as a warm, promotable
spare for model-outage fallback, depending on which of the two independent
toggles (`cross_model_divergence_check`, `fallback_standby_build`) is
active.

## Scope

**In scope:** invoking `generator` with a second model identifier;
invoking `verifier-orchestrator` against the resulting candidate; the
differential-behavior comparison itself, when in `divergence` mode.

**Out of scope:** deciding whether this component runs at all for a given
merge (`merge-orchestrator`'s job, reading the resolved toggle values);
promoting a standby build to canonical during an outage (D10's job,
elsewhere — this component only produces the candidate D10 later consumes).

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

- **R-XMODEL-001** — This component MUST only be invoked when at least one
  of `cross_model_divergence_check` or `fallback_standby_build` resolves to
  `enabled` and a second model is configured; if invoked anyway with neither
  condition true, it MUST report "not applicable" rather than silently
  running one of the two modes.
- **R-XMODEL-002** — MUST call `generator` with the **same** `SpecBundle`
  (same `spec_bundle_hash`, cold mode) but a **different** model identifier,
  writing the result to an isolated location — never overwriting the
  canonical `gen/<component>/` tree.
- **R-XMODEL-003** — MUST call `verifier-orchestrator` against the second
  candidate, using the same `acceptance.md` the canonical build was checked
  against.
- **R-XMODEL-004** — In `divergence` mode (`cross_model_divergence_check:
  enabled`): if the second candidate's verdict is `pass`, this component
  MUST compare its observable behavior against the canonical candidate's —
  running the same already-compiled/generated test inputs against both and
  diffing outputs. This comparison is deterministic once both candidates
  and the test inputs exist: no model or judgment is needed to tell whether
  two concrete outputs match.
- **R-XMODEL-005** — A divergence found under R-XMODEL-004 MUST be reported
  as a **merge-blocking spec defect**, naming the specific criterion(s)
  whose outputs diverged — actionable detail, not just "it diverged,"
  since the fix is tightening the spec, not picking a winner (D3).
- **R-XMODEL-006** — If the second candidate's verdict is `fail`, this MUST
  be logged, not blocking — a capability gap in the second model, not
  necessarily a spec defect, and MUST be recorded as a distinct outcome
  category from R-XMODEL-005's finding so the two are never conflated in
  provenance or metrics.
- **R-XMODEL-007** — In `standby-only` mode (`fallback_standby_build:
  enabled`, independent of whether `cross_model_divergence_check` is also
  enabled — D10's second regime): MUST still produce and verify the second
  candidate (R-XMODEL-002/003) but MUST NOT perform the R-XMODEL-004
  comparison — this is the cheaper path that buys the availability benefit
  without the divergence-detection cost.
- **R-XMODEL-008** — The resulting second-model candidate and its
  verification outcome MUST be exposed in a form D10's fallback-promotion
  mechanism can consume directly — this component's output **is** the
  "already-passing, continuously-exercised" standby build D10 depends on,
  not a separate artifact requiring reconciliation.
- **R-XMODEL-009** — Whether the second model is from a different vendor
  than the canonical pin MUST be recorded in the output (feeding the
  multi-model coverage metric, `notes/metrics.md`) but MUST NOT itself
  block anything — recommended, per D3/D10, never required.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`CrossCheckResult` schema).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

- The source of "fuzzed inputs" beyond the existing compiled/generated-test
  suite's own inputs (mentioned in D3 as part of the differential check) —
  whether this component generates additional inputs itself (e.g. via a
  property-based testing library) or only ever diffs against the existing
  test suite's inputs. Left open; the existing-inputs-only path is already
  a real, useful check and doesn't require this to be resolved first.

## Change log

- Initial draft.
