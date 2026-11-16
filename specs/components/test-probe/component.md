---
id: comp-test-probe
title: Test Probe
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Test Probe

## Purpose

Checks a generated test file for defects of its own, before it is ever
run against real code: syntax, undefined names, imports that cannot
resolve, fakes whose signatures disagree with the interface they stand
in for, and failures that happen before the code under test is reached.
A test that fails for its own reasons says nothing about the code, so it
must be repaired rather than counted.

## Scope

**In scope:** static checks of one test's source; one run of it against
a stub module that stands in for the component under test; a report of
findings with a severity each.

**Out of scope:** running a test against the real code; writing or
repairing a test; deciding whether a criterion passes.

## Definitions

The **stub module** is a module named like the component's module whose
every attribute is a stand-in that raises `HotdocsProbeStubReached`, an
exception derived from `BaseException`, when called. A test **reaches**
the code under test when that exception ends it.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

All are `kind: generated-test`: each passes a test's source text to
`probe` and checks the report.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- `D303`: initial spec; the fake-arity check moves here from
  `test-author`'s `R-AUTHOR-020`.
