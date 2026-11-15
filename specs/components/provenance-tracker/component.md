---
id: comp-provenance-tracker
title: Provenance Tracker
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-checker, comp-impact-analyzer, comp-capability-scenario-verifier]
realizes: [P-MERGE-VISIBILITY]
model_pin: claude-opus-5-5
sealed: false
---

# Provenance Tracker

## Purpose

Answers "would a merge pass right now" (`hotdocs verify`) by checking
every component's current provenance and checking-then-running every
intersecting capability's scenarios, across a scope — a blast radius or
the whole corpus — and reports one ready/not-ready verdict with
per-item detail. Also keeps a durable, local-only history of `hotdocs
generate` attempts (`AttemptRecord`) so a developer can see why a
component's provenance check is currently failing.

## Rationale

(`D88`, renamed from `merge-tracker`.) `merge-orchestrator`'s removal
(`D87`) left nothing that still needed a per-merge-attempt log —
`TrackingRecord` existed specifically to record outcomes of an
automated action that no longer exists. What a developer actually
needs is different: a live answer to "is everything ready," not a
history of past attempts at something no component does automatically
anymore. The per-component attempt history (`AttemptRecord`) is kept —
a developer running `hotdocs generate` still benefits from seeing why a
prior attempt failed, same as always.

`D92` briefly combined `hotdocs generate`/`check-capability`/`verify`
into one `hotdocs build` command, reasoning that this component
already had to compute whether provenance was current for every item
in scope — the only thing missing was acting on a miss. `D93` reversed
the component half of that: a developer genuinely wants `generate` and
`verify` as independently runnable commands, since generating new code
is a deliberate, potentially expensive action that `verify` should
never spring as a side effect. The capability half of `D92`'s
reasoning stands, unreversed: `verify` still checks-then-runs
`capability-scenario-verifier`'s own gauntlet for every intersecting
capability, since capability-scenario verification never produces new
source code, only exercises what already exists — triggering it from
`verify` costs a developer nothing they wouldn't expect. `D93` also
removes the dependency cycle `D92` introduced: this component no
longer calls `component-gate-runner` for anything, so
`component-gate-runner` can safely depend on this component again (to
call `write_attempt_record`) without creating a two-node cycle.

## Scope

**In scope:** for a given scope (`changed_ids`, via `impact-analyzer`,
or the whole corpus), checking `provenance-checker` for every component
— a pure, read-only check, never triggering generation (`R-TRACK-009`,
`D93`) — and checking-then-running `capability-scenario-verifier`'s
`run_capability_gates` for every intersecting capability (`R-TRACK-010`,
unreversed by `D93`), then reporting one `ready` verdict plus per-item
detail; writing one `AttemptRecord` per `hotdocs generate` attempt,
taken as direct parameters from `component-gate-runner`
(`R-TRACK-004`/`007`); exposing `last_requirement_failures` as a pure,
read-only convenience over that history (`R-TRACK-008`).

**Out of scope:** deciding whether a merge *should* proceed — nothing
gates on this component's output (`D87`; a human reads `hotdocs
verify`'s verdict and decides); triggering component generation on a
miss — that is `hotdocs generate`'s own job, by name, never a side
effect of checking readiness (`D93`); re-deriving `provenance-checker`'s
or `capability-scenario-verifier`'s own hit/miss logic — this component
calls their real functions, never re-implements them against raw
`.provenance.json`/capability-provenance files itself.

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

See the decisions, `D25` onward; `D292` makes usage errors print their reason.
