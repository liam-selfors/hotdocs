---
id: comp-provenance-tracker
title: Provenance Tracker
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-checker, comp-impact-analyzer, comp-capability-scenario-verifier, comp-secret-scanner]
realizes: [P-MERGE-VISIBILITY]
model_pin: claude-opus-5-5
sealed: false
---

# Provenance Tracker

## Purpose

Answers "would a merge pass right now" (`hotdocs verify`) by checking
every component's current provenance and checking-then-running every
intersecting capability's scenarios, across a scope — a blast radius or
the whole corpus — and reports one ready/not-ready verdict with
per-item detail. Also keeps a durable, local-only history of `hotdocs
generate` attempts (`AttemptRecord`) so a developer can see why a
component's provenance check is currently failing.

## Rationale

A live answer to "is everything ready" (`D87`, `D88`). `verify` never
generates code (`D93`), so `component-gate-runner` can depend on this
component without a cycle; capability scenarios only exercise existing
code. An unanswerable blast radius is not ready (`D350`).

## Scope

**In scope:** `check_readiness` over a blast radius or the whole
corpus; `AttemptRecord`s and `last_requirement_failures`.

**Out of scope:** deciding whether a merge proceeds (`D87`); generating
on a miss (`D93`); re-deriving `provenance-checker`'s or
`capability-scenario-verifier`'s hit/miss logic.

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

None.

## Change log

The decisions from `D25`, lately `D292`, `D368` and `D371`.
