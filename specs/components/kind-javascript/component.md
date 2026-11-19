---
id: comp-kind-javascript
title: Kind javascript
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Kind javascript

## Purpose

The adapter for the `javascript` asset kind: it checks that a generated
`.js` file is a self-contained ES module, lists its exports, checks that
Node 24 or later is available, runs one export with JSON arguments in a
sandboxed `node` process, and lists and applies the token mutations that
measure how well a test suite checks the module.

## Rationale

`D343` builds asset kinds with `javascript` first, so JavaScript is
declared as a file of its own and mutated over the whole file instead of
inside Python strings. The adapter carries out
`specs/asset-kinds/javascript.md` through the interface every adapter
shares, `specs/architecture/asset-kinds.md`. Its own Node driver is kept
short so that the adapter passes the rule it helps enforce: no
JavaScript of 200 characters or more inside a Python string.

## Scope

**In scope:** layout checks, export names, the Node version check, running
one export, strength sites and applying one.

**Out of scope:** deciding which assets a component declares, scoring
mutants, running pytest, installing Node, browsers and the DOM.

## Definitions

The **scan** is the tokenizer `interface/library.md` states; layout
checks and strength sites both use it.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

All are `kind: generated-test`, calling the module's functions on
JavaScript files a test writes under `tmp_path`.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Regular expression literals are not recognised by the scan: a `/`
  is always an operator, so a regex holding a quote or `//` can
  misplace sites. Generator guidance could forbid regex literals, or
  the scan could learn them.

## Change log

- `D343`: initial spec.
