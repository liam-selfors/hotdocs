---
id: comp-docs-site-renderer
title: Docs Site Renderer
status: draft
owners: [pipeline-team]
depends_on: [comp-corpus-graph-builder, comp-kind-javascript]
realizes: [P-AMBIGUITY-GATE]
sealed: false
assets: [javascript:static/app.js]
---

# Docs Site Renderer

## Purpose

Renders `verification/corpus-graph.json` into the interactive graph/docs
explorer — a pure presentation layer over data the pipeline already
computed, nothing more.

## Rationale

The graph/docs explorer this renders was established as a product decision early on.

## Scope

**In scope:** rendering the DAG, the per-node detail view, and the
corpus-health dashboard, all directly from `corpus-graph.json`.

**Out of scope:** computing anything `corpus-graph.json` doesn't already
contain; hosting/deployment (a CI/infra concern, not this component's
behavior).

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`. Input only: `verification/corpus-graph.json` (`corpus-graph-builder`'s
output). This component produces no new data artifact of its own, only the
rendered site.

## Acceptance criteria

See `acceptance/`.

All criteria are `kind: generated-test` (`D43`) — rendering
already-computed data is pure, deterministic templating that needs no
model or judgment, but none are actually written in the step-phrase
grammar, so `kind: compiled` would not describe how they're really
verified. The DAG view's layout and search are pure exports of the
`javascript` asset `static/app.js`, tested through `asset_runner`
(`D343`).

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
- `D55`: first real implementation, passed all 6 `AC-DOCS-*` criteria
  on the first real `generate()` attempt. Found `.gitignore` had no
  `/dist/` entry at all — fixed there, not in this component's own
  (already-correct) code. See `verification/docs-site-renderer/
  BOOTSTRAP.md`.
- `D343`: the DAG view's JavaScript moves out of a Python string into
  the declared `javascript` asset `static/app.js`
  (`interface/assets/app.js.md`), inlined once as a module script. The
  existing by-type column layout and id search are now stated exactly:
  new `R-DOCS-008`, `R-DOCS-009`, `AC-DOCS-009`–`AC-DOCS-011`.
