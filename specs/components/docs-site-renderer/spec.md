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

- **R-DOCS-001** — MUST render an interactive, clickable, searchable DAG
  from `corpus-graph.json`'s `nodes`/`edges` — one node per product
  capability, component, and var; edges for `depends_on`, `realizes`, and
  `uses_var` (D9).
- **R-DOCS-002** — For each component node, the detail view MUST show:
  rendered `spec.md`/`interface.md`/`acceptance.md`/`constraints.md`
  content; its `R-id` list with live status; acceptance criteria broken out
  by `kind` with verification result; provenance (model pin, prompt
  version, last cold-regen timestamp, freshness relative to D1); size vs.
  D2 caps, color-coded; the verification-toggle state actually in effect
  (`cross_model_divergence_check`, `fallback_standby_build`); `sealed`/
  pinned-override exemption status; owners — exactly D9's enumerated list,
  nothing added, nothing dropped.
- **R-DOCS-003** — MUST render a corpus-health dashboard surfacing
  `notes/metrics.md`'s computable numbers (requirement coverage,
  orphan rates, size-cap distribution, and the rest D9 already names).
- **R-DOCS-004** — The rendered site MUST be a pure function of
  `corpus-graph.json` — no second data source, no computation this
  component performs itself beyond presentation.
- **R-DOCS-005** — MUST be rebuilt on every merge to `main`, never a
  scheduled job (D9); the rendered output MUST NOT be committed — it is a
  CI build artifact, deployed to a docs host (D9's explicit
  committed-manifest-vs-built-site split).
- **R-DOCS-006** — MUST make no model calls — a pure rendering step.

## Interfaces

See `interface.md`.

## Data

Input only: `verification/corpus-graph.json` (`corpus-graph-builder`'s
output). This component produces no new data artifact of its own, only the
rendered site.

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
