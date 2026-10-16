---
id: comp-verifier-orchestrator
title: Verifier Orchestrator
status: draft
owners: [pipeline-team]
depends_on: [comp-criterion-compiler, comp-generator, comp-test-author]
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
components, D7/D12); *performing* an `llm-judge` evaluation or *authoring*
`generated-test` code (this component dispatches to an injectable judge and
an injectable `test_author` and records their results — it does not itself
judge or author anything, see the note below); **re-deciding a criterion's
declared `kind`** — `compiled`/`generated-test`/`llm-judge` is fixed at
spec-authoring time in `acceptance.md`, lint-checked (R-LINT-010), and never
reconsidered here. Giving this component (or `test-author`) the power to
override that declaration at verification time was considered and
explicitly rejected: it would make `kind:` advisory rather than normative,
and would turn this component's own dispatch logic into a judgment call,
breaking the determinism D13's cache-key validity and R-VERIFY-008's
idempotency claim both depend on.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

- **R-VERIFY-001** — For every `compiled`-kind criterion in a component's
  `acceptance.md`, this component MUST invoke `criterion-compiler` to
  produce test scaffolding, execute it against `gen/<component>/`, and
  record a pass/fail per criterion.
- **R-VERIFY-002** — For every `generated-test`-kind criterion, this
  component MUST obtain the test code — from cache if already authored for
  this criterion's content, or by dispatching to an injectable
  `test_author` callable otherwise (R-VERIFY-009) — execute it against
  `gen/<component>/`, and record a pass/fail per criterion.
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
- **R-VERIFY-009** — For a `generated-test`-kind criterion with no cached
  test yet, this component MUST dispatch to an injectable `test_author`
  callable, passing exactly the `CriterionBundle` `spec-bundle-assembler`
  produces for that criterion, and use the returned test code. **This
  component's role here is dispatch and recording, identical in shape to
  R-VERIFY-003's handling of `llm-judge`** — the actual authoring happens
  inside whatever callable is injected, never in this component's own
  logic, which is why this requirement, like R-VERIFY-003, is `kind:
  compiled` despite coordinating non-deterministic work.
- **R-VERIFY-010** — Unlike a `skipped` `llm-judge` finding, a
  `generated-test` criterion with no cached test and no `test_author`
  configured MUST be recorded as `fail`, not `skipped`. The two `kind`s
  differ in exactly this way: `llm-judge` is for qualities no test could
  capture even in principle, so "not evaluated" is a legitimate, visible
  gap (D10's posture). A `generated-test` criterion exists specifically
  *because* a real, mutation-tested check is possible for it — an
  unauthored one isn't a degraded-but-acceptable state, it's a verification
  gap the mutation-score gate (R-VERIFY-006) already presumes doesn't
  exist.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`VerificationReport` schema).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None. The gap this spec originally surfaced — which component authors
`generated-test` code — is resolved: `test-author`, invoked via the
`test_author` injectable callable (R-VERIFY-009), the same pattern already
established for `judge`.

## Change log

- Initial draft.
