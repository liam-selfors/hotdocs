---
id: comp-merge-tracker-ui
title: Merge Tracker UI
status: draft
owners: [pipeline-team]
depends_on: [comp-merge-tracker]
realizes: [P-MERGE-VISIBILITY]
sealed: false
---

# Merge Tracker UI

## Purpose

A local, per-developer view of `.hotdocs/tracking/` — the same role
`docs-site-renderer` plays for `corpus-graph.json`, applied to a
genuinely different kind of data with a genuinely different lifecycle.
It is a local dev tool, run by one developer against their own
machine's tracking history, not a published site.

## Rationale

`docs-site-renderer`'s output is a **CI build artifact**, published
somewhere shared, rendering **committed** corpus state (D9). This
component's data is **local-only, gitignored, per-developer** (D22) —
it cannot be a CI artifact, because CI has no `.hotdocs/` to render.

## Scope

**In scope:** rendering `.hotdocs/tracking/*.json` (via `merge-tracker`'s
documented `TrackingRecord` shape) as a per-component status view across
recent merge attempts; the one action this view needs is "re-run the
merge," which is not a feature this component implements — it is already
the correct, complete recovery path (`R-MERGE-018`) a developer invokes
themselves, outside this UI, same as any other `hotdocs merge` call.

**Out of scope:** a dedicated retry/resume action wired into this UI (per
the point above, there is nothing to wire — re-running the merge command
*is* the action, and building a button that just re-runs it on the
developer's behalf is a thin convenience this spec doesn't commit to
yet, not a gap); cross-developer or cross-machine aggregation (explicitly
deferred, `notes/initial-ideas.md` §14); any read of `specs/`,
`corpus-graph.json`, or anything else committed — if a future version
wants to show blast-radius context alongside tracking data, that is a
deliberate, separate extension (joining this component's data with
`specs/architecture/graph-query-engine.md`'s), not assumed here.

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

Six criteria, mixed `kind`: five are `compiled` (rendering/absence logic
and the serve command's static-only behavior, each a pure function of
its inputs, same case `docs-site-renderer` already makes); `AC-UI-001` is
`generated-test`, since asserting that DuckDB-WASM's `read_json` actually
runs correctly in a real browser environment needs an executable check,
not graph/text analysis.

## Non-functional constraints

See `constraints.md`.

## Open questions

- ~~How a developer actually opens this locally~~ — resolved
  (`R-UI-006`): a trivial local static-file server (`hotdocs track ui
  serve`), not `file://` — removes the CORS inconsistency across
  browsers entirely rather than leaving it to chance per developer.
- ~~Whether this component should eventually consume
  `specs/architecture/graph-query-engine.md`'s corpus graph too..., making
  this and `docs-site-renderer` converge into one UI...~~ — resolved
  (`D37`): staying separate, by decision rather than by default. The
  Scope section above already rules this out ("any read of `specs/`,
  `corpus-graph.json`, or anything else committed" is out of scope) for
  the reason restated here: committed, CI-rendered data and local,
  gitignored, per-developer data have genuinely different lifecycles,
  and nothing has asked for the convenience of one shared webpage badly
  enough to justify coupling them. Revisit only if a concrete
  cross-referencing need actually surfaces — not as a standing TODO.

## Change log

- Initial draft.
- `D37`: closed the `docs-site-renderer` convergence question — staying
  separate is the decision, not a deferral.
- `D39`: "cache hit" renamed "provenance hit" (`R-UI-002`), following
  `TrackingRecord`'s own field rename.
