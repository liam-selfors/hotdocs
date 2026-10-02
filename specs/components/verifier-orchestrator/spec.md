---
id: comp-verifier-orchestrator
title: Verifier Orchestrator
status: draft
owners: [pipeline-team]
depends_on: [comp-criterion-compiler, comp-generator]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
sealed: false
---

# Verifier Orchestrator

## Purpose

Runs every applicable verification gate against one component's generated
output and produces a single, structured pass/fail verdict: `compiled`
criteria (via `criterion-compiler`), `generated-test` criteria, `llm-judge`
criteria, the contract/property tests derived from `interface.md`/`Data`,
and the interface drift check.

## Scope

**In scope:** dispatching each acceptance criterion to the right checking
mechanism by its declared `kind`; running the interface drift check;
aggregating mutation scores; producing one `VerificationReport`.

**Out of scope:** the cross-model divergence check (`cross-model-divergence-
checker`'s job — a different gate, D3); the license/secret scans (separate
components, D7/D12); *performing* an `llm-judge` evaluation (this component
dispatches to an injectable judge and records the result — it does not
itself judge anything, see the note below).

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

- **R-VERIFY-001** — For every `compiled`-kind criterion in a component's
  `acceptance.md`, this component MUST invoke `criterion-compiler` to
  produce test scaffolding, execute it against `gen/<component>/`, and
  record a pass/fail per criterion.
- **R-VERIFY-002** — For every `generated-test`-kind criterion, this
  component MUST execute the already-generated test code (produced
  separately, per D4/D5's independent-path mechanism) against
  `gen/<component>/` and record a pass/fail per criterion.
- **R-VERIFY-003** — For every `llm-judge`-kind criterion, this component
  MUST invoke an injectable judge callable and record its pass/fail +
  rationale, or record `skipped` when no judge is configured — the same
  graceful-degradation posture `spec-linter`'s R-LINT-015 established, now a
  fourth instance. **This component's own behavior here is dispatch and
  recording, not judgment** — the judging happens inside whatever callable
  is injected, which is why every requirement in this component, including
  this one, is `kind: compiled`: coordinating non-deterministic work is
  itself a deterministic activity.
- **R-VERIFY-004** — This component MUST perform the interface drift check:
  the generated code's actual public interface MUST match `interface.md`
  exactly; any divergence MUST be recorded as a hard failure.
- **R-VERIFY-005** — The overall verdict MUST be `fail` if any `compiled` or
  `generated-test` criterion fails, or the interface drift check fails, or
  any `llm-judge` criterion is evaluated and fails. A `skipped` `llm-judge`
  finding MUST NOT by itself cause an overall `fail` — `skipped` means "not
  evaluated," not "violated," consistent with `spec-linter`'s existing
  severity semantics.
- **R-VERIFY-006** — For `generated-test`-kind criteria, this component MUST
  compute and report the mutation score, and the overall verdict MUST be
  `fail` if it falls below the published bar (80% general / 90%
  freeform-derived, `SPEC_GUIDELINES.md` §5).
- **R-VERIFY-007** — This component MUST produce one structured
  `VerificationReport` — per-criterion results, mutation scores, interface
  drift result, and the overall verdict — consumed by `provenance-writer`
  and `review-packet-builder`.
- **R-VERIFY-008** — Given the same `gen/<component>/` content, the same
  `acceptance.md`, and a judge callable that itself returns consistent
  results, this component's own orchestration logic MUST be idempotent —
  re-running it MUST reproduce the same `VerificationReport`. This is a
  claim about this component's *own* determinism, not a claim that
  `llm-judge` evaluations are reproducible in general (they may not be,
  which is exactly why this requirement is phrased conditionally on the
  judge callable's own consistency, not as a blanket idempotency claim).

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`VerificationReport` schema).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Where "the already-generated test code" for `generated-test`-kind
  criteria (R-VERIFY-002) actually comes from — which component authors it,
  and at what pipeline stage — is referenced throughout the brainstorm (D4's
  "independent generation path") but no component in this architecture is
  explicitly assigned that job yet. Flagged, not resolved here; a real gap
  this spec surfaced rather than quietly assumed an answer for.

## Change log

- Initial draft.
