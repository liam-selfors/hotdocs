---
id: comp-kind-css
title: Kind css
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Kind css

## Purpose

The adapter for the `css` asset kind: it checks that a generated `.css`
file is a plain stylesheet a page can inline, lists its tokens and
classes, answers questions about its rules, tokens and colour contrast
in Python, and lists and applies the declaration deletions that measure
how well a test suite checks it.

## Rationale

See `D386`.

## Scope

**In scope:** layout checks, surface names, the parse behind
`asset_runner`, contrast ratios, strength sites and applying one.

**Out of scope:** browsers, computed styles, cascade and specificity,
deciding which assets a component declares, scoring mutants.

## Definitions

The **parse** is the scan and rule structure
`specs/architecture/asset-kind-css.md` "Layout" states; every function
reads the asset through it.

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

- Nested `@media`, `@supports` and `@layer` are rejected; a page that
  needs one is a change to the kind's definition.

## Change log

`D386`.
