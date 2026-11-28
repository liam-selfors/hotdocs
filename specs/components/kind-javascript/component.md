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

See `D343`.

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

## Non-functional constraints

See `constraints.md`.

## Open questions

- Regular expression literals are not recognised by the scan: a `/`
  is always an operator, so a regex holding a quote or `//` can
  misplace sites. Generator guidance could forbid regex literals, or
  the scan could learn them.

## Change log

`D343`.
