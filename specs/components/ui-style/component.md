---
id: comp-ui-style
title: UI style
status: draft
owners: [pipeline-team]
depends_on: [comp-kind-css, comp-driver-browser]
realizes: [P-MERGE-VISIBILITY]
model_pin: claude-opus-5-5
sealed: false
assets: [css:static/style.css]
drivers: [browser]
---

# UI style

## Purpose

The one stylesheet every page `hotdocs` writes inlines: the colour,
type and spacing tokens, their dark values, and the few base rules and
classes `specs/architecture/visual-style.md` names, with a small module
that hands the stylesheet to a page.

## Rationale

See `D386`. A colour lives here once; changing it regenerates this
component, and the pages that inline it are re-verified, not
regenerated (`D379`).

## Scope

**In scope:** the stylesheet's tokens and rules, reading it, the
`<style>` element a page writes.

**Out of scope:** page layout, markup, scripts, icons and fonts files.

## Definitions

See `specs/architecture/visual-style.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

None.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

Standard library only; the module reads its own asset and nothing else.

## Open questions

None.

## Change log

`D386`.
