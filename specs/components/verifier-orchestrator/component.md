---
id: comp-verifier-orchestrator
title: Verifier Orchestrator
status: draft
owners: [pipeline-team]
depends_on: [comp-criterion-compiler, comp-generator, comp-test-author, comp-spec-bundle-assembler]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
model_pin: claude-opus-5-5
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

**Out of scope:** the license/secret scans (separate components);
*performing* an `llm-judge` evaluation or *authoring*
`generated-test` code (this component dispatches to an injectable judge and
an injectable `test_author` and records their results — it does not itself
judge or author anything); **re-deciding a criterion's declared `kind`**,
which is fixed in `acceptance/` and lint-checked (R-LINT-010).

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

Deterministic dispatch-and-record logic, testable by mocking
`criterion-compiler`, the judge and `test_author`.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

See the decisions, `D27` onward; `D320` adds the criterion header check.
