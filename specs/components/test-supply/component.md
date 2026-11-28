---
id: comp-test-supply
title: Test Supply
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-test-probe]
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Test Supply

## Purpose

Supplies one `generated-test` criterion's test, ready to run: the
committed test while it is current and sound, otherwise one authored
afresh from the criterion's bundle, checked by the test probe before it
is ever run against code. When no sound test can be had, it says why,
so the criterion fails as a test problem rather than a code problem.

## Scope

**In scope:** finding the committed test; deciding whether it is
current; calling the test author, and again on a transient failure;
probing; one re-authoring of a test that fails its probe; discarding a
committed test shown faulty.

**Out of scope:** running a test against the code; mutation; the verdict.

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
