---
id: comp-provenance-tracker
title: Provenance Tracker
status: draft
owners: [pipeline-team]
depends_on: [comp-component-gate-runner, comp-impact-analyzer, comp-capability-scenario-verifier]
realizes: [P-MERGE-VISIBILITY]
sealed: false
---

# Provenance Tracker

## Purpose

`hotdocs build`: for a given scope (a single component, a blast
radius, or the whole corpus), brings every component and every
intersecting capability to current, passing provenance — generating or
re-verifying only what isn't already current — and reports one
ready/not-ready verdict with per-item detail. Also keeps a durable,
local-only history of attempts (`AttemptRecord`) so a developer can see
why a component's provenance check is currently failing.

## Rationale

(`D88`, renamed from `merge-tracker`.) `merge-orchestrator`'s removal
(`D87`) left nothing that still needed a per-merge-attempt log —
`TrackingRecord` existed specifically to record outcomes of an
automated action that no longer exists. `D92` went one step further
than the live read-only query `D88` first introduced: this component
already had to compute, for every item in scope, whether its
provenance was current — the only thing missing was acting on a miss
instead of just reporting it, the same check-then-do pattern
`component-gate-runner`/`capability-scenario-verifier` already use
internally. Combining `hotdocs generate`/`hotdocs check-capability`/
`hotdocs verify` into this one command meant breaking a real
dependency cycle: `component-gate-runner` writes its own
`AttemptRecord`s directly now (`R-GATE-008`), rather than calling into
this component for it, so this component can depend on
`component-gate-runner` to trigger its gauntlet without a two-node
cycle.

## Scope

**In scope:** for a given scope (`changed_ids`, via `impact-analyzer`,
or the whole corpus), calling `component-gate-runner`'s
`run_component_gates` for every component and
`capability-scenario-verifier`'s `run_capability_gates` for every
intersecting capability — each already checks its own provenance first
and skips real work on a hit, so this component never re-derives
hit/miss logic itself — and reporting one `ready` verdict plus
per-item detail (`R-TRACK-009`/`010`); reading `.hotdocs/attempts/`
(written directly by `component-gate-runner`, `R-GATE-008`) for
`last_requirement_failures` (`R-TRACK-008`), a pure, read-only
convenience for `--retry-feedback`.

**Out of scope:** deciding whether a merge *should* proceed — nothing
gates on this component's output (`D87`; a human reads `hotdocs
build`'s verdict and decides); the actual generation/verification/scan
mechanics (`component-gate-runner`'s own job) or capability-scenario
dispatch mechanics (`capability-scenario-verifier`'s own job) — this
component only decides *when* to call each, never how either runs.

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

All criteria are `kind: compiled` — sequencing already-defined calls and
assembling their results into one report is pure, deterministic logic;
nothing here needs a model or judgment itself (the components it calls
may make model calls internally, but that is their own concern, not
this one's).

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft, as `merge-tracker`.
- `D25`: closed the best-effort/visibility open question for
  `write_tracking_record` — superseded below.
- `D29`: `TrackingRecord.components[].cache_hit` renamed
  `provenance_hit` — superseded below.
- `D86`: `write_attempt_record`'s caller changed from
  `merge-orchestrator` to `component-gate-runner` — superseded below.
- `D87`/`D88`: renamed `provenance-tracker`. `write_tracking_record`/
  `TrackingRecord`/`hotdocs track query` removed entirely. New:
  `check_readiness`/`VerifyReport` (`R-TRACK-009`/`010`), exposed as
  `hotdocs verify` — a read-only "will a merge pass" check.
- `D92`: `check_readiness` now triggers work instead of only reporting
  on it — calls `component-gate-runner`'s and
  `capability-scenario-verifier`'s own gauntlets directly, exposed as
  `hotdocs build`, replacing `hotdocs generate`/`check-capability`/
  `verify` entirely. `depends_on` swaps `provenance-checker` for
  `component-gate-runner` directly. `write_attempt_record` removed —
  `component-gate-runner` writes `AttemptRecord`s itself now
  (`R-GATE-008`), breaking what would otherwise have become a
  dependency cycle; this component only reads them.
