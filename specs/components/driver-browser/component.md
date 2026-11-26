---
id: comp-driver-browser
title: Browser Test Driver
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Browser Test Driver

## Purpose

Lets a component's tests load a page the component wrote or serves in a
headless Chromium and use it as a person would: clicking, typing,
pressing keys, scrolling and dragging, then reading what the page shows,
what it logged as errors, what it tried to fetch, and what it
downloaded. It installs its own browser the first time a project needs
one.

## Scope

**In scope:** provisioning Playwright and Chromium into the project's
environment directory; the `browser` fixture's session, page and
element objects; isolation of the driven page; the test author's
guidance.

**Out of scope:** judging how a page looks; comparing screenshots.

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

`D373`.
