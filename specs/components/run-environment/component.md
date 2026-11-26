---
id: comp-run-environment
title: Run Environment
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Run Environment

## Purpose

Provisions what a component's or capability's tests need before any of
them runs: the environment of each asset kind it declares, the `python`
one first, and each test driver it declares. It reports what it found
for provenance and supplies the pytest plugin that gives every run the
`asset_runner` fixture and each driver's fixture.

## Scope

**In scope:** finding and provisioning asset-kind and driver adapters;
the provenance entries for them; writing the pytest plugin and the
settings a run needs to load it.

**Out of scope:** running tests; mutation; deciding a verdict.

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
