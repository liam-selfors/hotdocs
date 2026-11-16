---
id: comp-surface-checker
title: Surface Checker
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Surface Checker

## Purpose

Rejects a generated candidate cheaply, before the long verification,
when it cannot work in place: it does not import, it uses a name one of
its dependencies does not have, or, for a component with a command
line, it mishandles an unknown argument. These are the failures that
otherwise surface only when a user first runs the tool.

## Scope

**In scope:** an import of the candidate; the names it uses on each
direct dependency's module; a smoke run of its `main` with an unknown
argument when it implements `specs/architecture/cli-conventions.md`.

**Out of scope:** behavior the acceptance criteria check; the
candidate's own interface (the verifier's interface drift check).

## Definitions

A **use** of a dependency is an `<alias>.<name>` in the candidate's
source, `<alias>` the dependency's module name or a variable assigned on
a line that loads it.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

All are `kind: generated-test` over a synthetic `repo_root`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- `D311`: initial spec; the import and dependency checks come from
  `tools/bootstrap_component.py`'s gates.
