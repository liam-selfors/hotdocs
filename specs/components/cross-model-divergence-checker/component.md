---
id: comp-cross-model-divergence-checker
title: Cross-Model Divergence Checker
status: draft
owners: [pipeline-team]
depends_on: [comp-generator, comp-verifier-orchestrator, comp-cache-manager]
depends_on_guarantees: [G-CACHE-001]
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

Declares `depends_on_guarantees: [G-CACHE-001]` — the D16 worked example.
This component's own correctness genuinely depends on `cache-manager`'s
consistency guarantee specifically (concurrent writes for the same cache
key are safe under last-write-wins): the canonical and second-model builds
checked in the same merge are exactly the kind of concurrent caller this
guarantee is about. It does *not* depend on `cache-manager`'s other
properties (store-error fail-closed behavior, CLI inspection, etc.) in any
way its own logic cares about — so a future change to *those* should not,
and now will not, pull this component into an unrelated blast radius.

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

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

All nine criteria are `kind: compiled`. This might look surprising for a
component whose whole point is comparing two *model-generated* candidates —
but once both candidates exist and a test suite exists, "do these two
concrete outputs match" is a mechanical equality check, no judgment
involved. The fifth component in this corpus whose entire acceptance set is
`compiled` (after `impact-analyzer`, `cache-manager`,
`spec-bundle-assembler`, `verifier-orchestrator`) — judgment and model
calls happen inside `generator` and (optionally) `llm-judge` criteria this
component merely coordinates, never in this component's own logic.

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
