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
line, it mishandles an unknown argument, or a declared asset lacks
a name its interface states. These are the failures that
otherwise surface only when a user first runs the tool.

## Scope

**In scope:** the `python` environment the candidate runs in; an
import of the candidate; the names it uses on each
direct dependency's module; a smoke run of its `main` with an unknown
argument when it implements `specs/architecture/cli-conventions.md`;
the names each declared asset provides, through its kind's adapter.

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
- `D343`: `R-SURF-005`, `AC-SURF-005`, `AC-SURF-006`: declared assets'
  surfaces are checked through their kinds' adapters; `R-SURF-004`
  orders the new findings; `surface-checker@1.1.0`.
- `D344`: `R-SURF-006`, `AC-SURF-007`: the candidate and its
  dependencies are imported under the interpreter the `python` adapter's
  `provision` reports, and a failed provision is one `environment`
  finding; `surface-checker@1.2.0`.
- `D362`: `R-SURF-002` reads uses from the syntax tree.
