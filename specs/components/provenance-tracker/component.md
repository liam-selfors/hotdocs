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

(`D88`, renamed from `merge-tracker`.) A developer needs a live answer
to "is everything ready", not a log of merge attempts (`D87`); the
per-component attempt history stays, to show why a prior attempt
failed. `verify` never generates code (`D93`, reversing the component
half of `D92`), but it does check-then-run capability scenarios, which
only exercise existing code. Because this component never calls
`component-gate-runner`, that component can depend on this one without
a cycle. An unanswerable blast radius is reported as not ready, never
as an empty, ready scope (`D350`).

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

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

See the decisions, `D25` onward; `D292` makes usage errors print their reason;
`D368` words a capability that is not passing.
