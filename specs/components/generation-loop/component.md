---
id: comp-generation-loop
title: Generation Loop
status: draft
owners: [pipeline-team]
depends_on: [comp-generator, comp-agentic-generator, comp-surface-checker, comp-verifier-orchestrator, comp-test-author, comp-llm-endpoint]
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Generation Loop

## Purpose

Turns a spec bundle into a verified candidate with a bounded number of
attempts: generate, check the surface, verify, and on a failure try
again with the failed requirement ids as the only feedback. Builds the
test-author and judge callables verification needs.

## Scope

**In scope:** the attempt loop and its retry rules; the feedback each
attempt carries; committing a passing candidate to the cache; the
`test_author` and `judge` closures.

**Out of scope:** provenance and attempt records (its caller's, through
`on_attempt`); license and secret scans; deciding a component is sealed.

## Definitions

An **attempt** is one generation followed, when it produced files, by a
surface check and, when that passed, a verification.

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

`D310`, `D343`.
