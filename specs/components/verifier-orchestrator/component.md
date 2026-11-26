---
id: comp-verifier-orchestrator
title: Verifier Orchestrator
status: draft
owners: [pipeline-team]
depends_on: [comp-criterion-compiler, comp-generator, comp-test-author, comp-spec-bundle-assembler, comp-run-environment, comp-test-supply, comp-mutation-scorer]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
model_pin: claude-opus-5-5
sealed: false
---

# Verifier Orchestrator

## Purpose

Runs every verification gate against one component's generated
output and its assets, and produces one structured verdict:
`compiled`, `generated-test` and `llm-judge` criteria, the mutation
score and the interface drift check.

## Scope

**In scope:** dispatching each criterion by its `kind`; running each
test; the drift check; the verdict, including the mutation bar; one
`VerificationReport`.

**Out of scope:** provisioning (`run-environment`), supplying tests
(`test-supply`), mutation (`mutation-scorer`); the license and secret
scans; judging or authoring anything (it dispatches to an injectable
judge and `test_author` and records their results).

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

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

See the decisions, `D27` onward; latest `D383` (split into
`run-environment`, `test-supply` and `mutation-scorer`).
