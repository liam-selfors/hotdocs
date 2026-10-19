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
criteria, the contract/property tests derived from `interface/`, and the
interface drift check.

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
spec-authoring time in `acceptance/`, lint-checked (R-LINT-010), and never
reconsidered here. Giving this component (or `test-author`) the power to
override that declaration at verification time was considered and
explicitly rejected: it would make `kind:` advisory rather than normative,
and would turn this component's own dispatch logic into a judgment call,
breaking the determinism D13's cache-key validity and R-VERIFY-008's
idempotency claim both depend on.

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

All nine criteria are `kind: compiled` — this component coordinates
checking mechanisms (some of which involve judgment or external calls), but
the coordination itself is deterministic dispatch-and-record logic, testable
by mocking `criterion-compiler` and the judge callable. A fourth component
in this corpus whose entire acceptance set is `compiled`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None. The gap this spec originally surfaced — which component authors
`generated-test` code — is resolved: `test-author`, invoked via the
`test_author` injectable callable (R-VERIFY-009), the same pattern already
established for `judge`.

## Change log

- Initial draft.
