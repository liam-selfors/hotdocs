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
explorer D9 describes — a pure presentation layer over data the pipeline
already computed, nothing more.

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

All six criteria are `kind: compiled` — rendering already-computed data is
pure, deterministic templating. A tenth component in this corpus with a
fully `compiled` acceptance set.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
