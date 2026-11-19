---
id: comp-provenance-tracker-ui
title: Provenance Tracker UI
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-tracker, comp-corpus-graph-builder, comp-kind-javascript]
realizes: [P-MERGE-VISIBILITY]
model_pin: claude-opus-5-5
sealed: false
assets: [javascript:static/app.js]
---

# Provenance Tracker UI

## Purpose

A static, self-contained page showing corpus readiness: every
component and capability in scope, colored by current provenance
status, for either a blast-radius or a whole-corpus view, with
per-node drill-down into `AttemptRecord` history and retry-feedback
suggestions for anything currently failing. The visual answer to the
same question `hotdocs verify` answers as an exit code, snapshotted at
build time.

## Rationale

(`D88`, renamed from `merge-tracker-ui`.) `merge-orchestrator`'s removal
(`D87`) retired the per-merge-attempt log this component used to
render; what replaced it (`provenance-tracker`'s live `VerifyReport`) is
naturally graph-shaped — components and capabilities as nodes, their
current provenance status as the thing being rendered — so this
component's own shape follows. Reading `corpus-graph-builder`'s
committed graph for topology, alongside `provenance-tracker`'s
local-only provenance state, is the first time this component crosses
the boundary its own `component.md` previously ruled out (`R-UI-004`,
old) — the concrete cross-referencing need that boundary's own open
question said would justify revisiting it has now actually surfaced.

## Scope

**In scope:** calling `provenance-tracker`'s `check_readiness` once per
build for the chosen scope (`R-UI-007`); reading `corpus-graph.json`
for topology (`R-UI-004`); mapping each node to a status (`R-UI-002`);
attaching `AttemptRecord` history and `last_requirement_failures` as
retry-feedback suggestions to failing or missing nodes (`R-UI-008`);
writing one self-contained page (`R-UI-001`) whose only script is the
asset `static/app.js`, filtering nodes by status (`R-UI-010`).

**Out of scope:** a "generate" action of its own (`R-UI-003`) — a
developer runs `hotdocs generate` themselves; any view-time query or
server (`R-UI-006`); any write except the page itself.

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

All `kind: generated-test` — every criterion needs a faked
`provenance-tracker` and real files on disk, which no fixed step
grammar can set up.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft, as `merge-tracker-ui`.
- `D16`: resolved how a developer opens this locally (`hotdocs track ui
  serve`, a trivial local static-file server, not `file://`).
- `D29`: "cache hit" renamed "provenance hit", following
  `TrackingRecord`'s own field rename — superseded below.
- `D87`/`D88`: renamed `provenance-tracker-ui`. No longer renders
  `TrackingRecord` history (removed, nothing produces it anymore) —
  renders `provenance-tracker`'s live `VerifyReport` as an interactive
  graph instead, now also reading `corpus-graph-builder`'s committed
  graph for topology (`R-UI-004`, reversing the prior "never reads
  committed corpus state" boundary now that a concrete need surfaced).
  `AttemptRecord`/retry-feedback drill-down kept, now graph-attached
  rather than a flat per-component list.
- `D93`: wording only — every reference to the since-reversed combined
  `hotdocs build` command now names `hotdocs generate` (the recovery
  action for a failing component) or `hotdocs verify` (the readiness
  query this UI visualizes), whichever it actually meant.
- `D154`: rebuilt as a build-time snapshot — `check_readiness` called
  once in Python, all data inlined into one `file://`-openable page.
  DuckDB-WASM, `duckpgq`, and `hotdocs track ui serve` dropped; the
  spec's static-page and render-`check_readiness` requirements could
  not both hold. Build takes `--model`, passed through. New
  `R-UI-009` (CLI).
- `D161`: `AC-UI-003`'s no-generate-action check excludes the
  `tracker-snapshot` data block; `R-UI-009` covers every CLI flag form.
  Cold-generated and landed (`mutation_score` 0.95).
- `D343`: the page's JavaScript moves out of a Python string into the
  declared `javascript` asset `static/app.js`
  (`interface/assets/app.js.md`), inlined once as a module script. New
  `R-UI-010` (status filter, decided by the pure `hiddenByStatus`),
  `AC-UI-010`, `AC-UI-011`.
