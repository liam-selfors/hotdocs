---
id: comp-mutation-scorer
title: Mutation Scorer
status: draft
owners: [pipeline-team]
depends_on: [comp-run-environment]
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Mutation Scorer

## Purpose

Measures how strong a component's passing tests are: it copies the
component's code into a sandbox, makes one small wrong change at a
time to its Python and to each declared asset, and reports the share of
those mutants the tests catch. A test that only passes where the
criterion ran, and fails in the sandbox, is reported as faulty.

## Scope

**In scope:** the mutation sandbox; the baseline run; the strength
sites of every asset kind and applying each alone; per-mutant runs and
timeouts; finding faulty tests when the baseline fails; one score.

**Out of scope:** choosing which tests to score; the bar a score must
meet; the verdict.

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

`D383`.
