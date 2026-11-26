---
id: comp-kind-python
title: Kind python
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Kind python

## Purpose

The adapter for the `python` asset kind: it checks that every `.py`
file of a component's code directory parses, lists the module's public
names, provides the Python environment the component's tests run in
(the project's own, built from its lock, or `hotdocs`' own), runs one
function with JSON arguments in a subprocess, and lists and applies the
mutations that measure how well a test suite checks the code.

## Rationale

See `D344`, `D159`, `D172`.

## Scope

**In scope:** the syntax check, public names, provisioning the
environment from `environments/python/requirements.lock`, running one
function, mutation sites and applying one.

**Out of scope:** running pytest, scoring mutants, `surface-checker`'s
import and dependency checks, writing or choosing a lock.

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

- The contract says an asset runs with no network and without
  `hotdocs`' own packages; with no lock this kind runs in `hotdocs`'
  environment by definition, and no network sandbox is applied.
- `surface` and `asset_runner` take the code directory only, so the
  module name comes from the directory's name and the interpreter from
  `HOTDOCS_PYTHON`; callers pass directories named by slug.

## Change log

`D344`.
