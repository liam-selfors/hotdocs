---
id: comp-provenance-tracker
title: Provenance Tracker
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-checker, comp-impact-analyzer, comp-capability-scenario-verifier]
realizes: [P-MERGE-VISIBILITY]
sealed: false
---

# Provenance Tracker

## Purpose

Answers "would a merge pass right now" (`hotdocs verify`) by
checking every component's and every intersecting capability's current
provenance across a scope — a blast radius or the whole corpus — and
reports one ready/not-ready verdict with per-item detail. Also keeps a
durable, local-only history of `hotdocs generate` attempts
(`AttemptRecord`) so a developer can see why a component's provenance
check is currently failing without having kept the CLI output.

## Rationale

(`D88`, renamed from `merge-tracker`.) `merge-orchestrator`'s removal
(`D87`) left nothing that still needed a per-merge-attempt log —
`TrackingRecord` existed specifically to record outcomes of an
automated action that no longer exists. What a developer actually
needs is different: a live answer to "is everything ready," not a
history of past attempts at something no component does
automatically anymore. The per-component attempt history
(`AttemptRecord`) is kept — a developer running `hotdocs generate`
still benefits from seeing why a prior attempt failed, same as always.

## Scope

**In scope:** for a given scope (`changed_ids`, via `impact-analyzer`,
or the whole corpus), checking `provenance-checker` for every component
and `capability-scenario-verifier`'s own provenance for every
intersecting capability, and reporting one `ready` verdict plus
per-item detail (`R-TRACK-009`/`010`); writing one `AttemptRecord` per
`hotdocs generate` attempt, taken as direct parameters from
`component-gate-runner` (`R-TRACK-004`/`007`); exposing
`last_requirement_failures` as a pure, read-only convenience over that
history (`R-TRACK-008`).

**Out of scope:** deciding whether a merge *should* proceed — nothing
gates on this component's output (`D87`; a human reads `hotdocs
verify`'s verdict and decides); re-deriving `provenance-checker`'s or
`capability-scenario-verifier`'s own hit/miss logic — this component
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

All criteria are `kind: compiled` — assembling already-computed facts
into one report is pure, deterministic logic; nothing here needs a
model or judgment.

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
  `merge-orchestrator` to `component-gate-runner`.
- `D87`/`D88`: renamed `provenance-tracker`. `write_tracking_record`/
  `TrackingRecord`/`hotdocs track query` removed entirely — nothing
  calls the former, and the latter's job (per-merge-attempt history)
  no longer corresponds to anything that happens automatically.
  `write_attempt_record`/`last_requirement_failures` kept unchanged.
  New: `check_readiness`/`VerifyReport` (`R-TRACK-009`/`010`), exposed
  as `hotdocs verify` — the canonical "will a merge pass" command.
