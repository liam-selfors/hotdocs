---
id: comp-provenance-tracker-ui
title: Provenance Tracker UI
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-tracker, comp-corpus-graph-builder]
realizes: [P-MERGE-VISIBILITY]
sealed: false
---

# Provenance Tracker UI

## Purpose

An interactive graph view of corpus readiness: every component and
capability, colored by current provenance status, navigable between a
blast-radius view and a whole-corpus view, with per-node drill-down
into `AttemptRecord` history and retry-feedback suggestions for
anything currently failing. The visual answer to the same question
`hotdocs verify` answers as an exit code.

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

**In scope:** rendering `corpus-graph-builder`'s graph as the topology
layer (`R-UI-004`); querying `provenance-tracker`'s `check_readiness`
for the currently-selected scope and coloring each node by its
provenance status (`R-UI-002`); navigation/filtering between a
blast-radius view (given a changed-ids set) and a whole-corpus view
(`R-UI-007`); per-node drill-down showing `AttemptRecord` history and
`last_requirement_failures`, surfaced as retry-feedback suggestions,
for any node currently failing or missing provenance (`R-UI-008`).

**Out of scope:** a "retry"/"resume" action of its own (`R-UI-003`) —
running `hotdocs generate` again is already the complete path, a
developer invokes it themselves, outside this UI; any write to
`specs/`, `gen/`, `verification/`, or `.hotdocs/` — this component only
ever reads.

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

Mixed `kind`: most are `compiled` (rendering/filtering logic, each a
pure function of its inputs, same case `docs-site-renderer` already
makes); one `generated-test` criterion checks that DuckDB-WASM's graph
query actually runs correctly in a real browser environment.

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
