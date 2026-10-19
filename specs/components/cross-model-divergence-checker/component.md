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

**Build status: deferred for the initial example-project build.** This
spec is complete and intended as the target design, but implementation is
not scheduled for the first build — the example project ships single-model
only for now. This costs nothing elsewhere in the corpus: single-model
operation was always a first-class, explicitly-designed degraded mode
(D10), not a fallback bolted on afterward — `merge-orchestrator` already
treats both toggles resolving to disabled-or-no-second-model as a plain
"not applicable" path (`R-XMODEL-001`), so no other component's spec
changes because of this deferral. Revisit once the single-model pipeline
is working end-to-end and there's a concrete need for either divergence
detection or outage resilience.

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
  test suite's inputs. Paused mid-analysis (not resolved) when this
  component's implementation was deferred; partial findings worth keeping
  for whenever work resumes:
  - As written, `R-XMODEL-004`'s "diffing outputs" has nothing concrete to
    diff — neither `VerificationReport` nor `CrossCheckResult` capture
    actual output *values*, only `pass`/`fail`/`skipped`. Since both
    candidates must pass the same literal assertions to reach this
    comparison, comparing verdicts alone is close to a no-op for
    `compiled`-kind criteria. The real signal lives in parts of the output
    the Gherkin assertion didn't pin — e.g. a `Then result.hit equals
    false` step only pins `.hit`; the rest of `result` is unchecked and
    could still diverge between models.
  - Candidate fix, not yet implemented: for `compiled`-kind criteria only
    (the one category where the step grammar guarantees a concrete,
    structured `result` value by construction), have `criterion-compiler`'s
    emitted test also serialize the full captured `result` — written
    before the assertion runs, so it's captured regardless of pass/fail —
    and give `CrossCheckResult` a field holding the canonical-vs-second-
    candidate pair for structural diffing. Deliberately scoped to
    `compiled` only; `generated-test` code has no guaranteed structured
    value to extract generically, and `llm-judge` isn't about exact match.
  - That fix has its own prerequisite gap: `R-XMODEL-003` requires running
    `verifier-orchestrator` "against the second candidate," but
    `verifier-orchestrator`'s own requirements (`R-VERIFY-001`/`002`)
    hardcode execution against `gen/<component>/` — there's no way today to
    point it at the isolated location `R-XMODEL-002` writes the second
    candidate to. Candidate fix: an optional `source_root` parameter on
    `verify()`, defaulting to today's behavior.
  - True fuzzing (synthesizing novel inputs, not just diffing existing
    ones) stays separately deferred regardless of the above — a distinct
    capability needing new machinery (e.g. property-based generation
    against `interface/` type schemas), not a natural extension of fixing
    the "nothing to diff" gap.

## Change log

- Initial draft.
