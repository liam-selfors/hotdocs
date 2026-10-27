---
id: comp-docs-site-renderer
title: Docs Site Renderer
status: draft
owners: [pipeline-team]
depends_on: [comp-corpus-graph-builder]
realizes: [P-AMBIGUITY-GATE]
sealed: false
---

# Docs Site Renderer

## Purpose

Renders `verification/corpus-graph.json` into the interactive graph/docs
explorer — a pure presentation layer over data the pipeline already
computed, nothing more.

## Rationale

D9 is the product decision describing the explorer this renders.

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

All six criteria are `kind: generated-test` (`D59`) — rendering
already-computed data is pure, deterministic templating that needs no
model or judgment, but none are actually written in the step-phrase
grammar, so `kind: compiled` would not describe how they're really
verified.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
- `D71`: first real implementation, passed all 6 `AC-DOCS-*` criteria
  on the first real `generate()` attempt. Found `.gitignore` had no
  `/dist/` entry at all — fixed there, not in this component's own
  (already-correct) code. See `verification/docs-site-renderer/
  BOOTSTRAP.md`.
