---
id: comp-provenance-tracker
title: Provenance Tracker
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-checker, comp-impact-analyzer, comp-capability-scenario-verifier]
realizes: [P-MERGE-VISIBILITY]
model_pin: claude-sonnet-5
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

- Initial draft, as `merge-tracker`. `D25`/`D29`/`D86` superseded below.
- `D87`/`D88`: renamed `provenance-tracker`. `write_tracking_record`/
  `TrackingRecord`/`hotdocs track query` removed entirely. New:
  `check_readiness`/`VerifyReport` (`R-TRACK-009`/`010`), exposed as
  `hotdocs verify` — a read-only "will a merge pass" check.
- `D92`/`D93`: `D92` briefly made `check_readiness` trigger work
  (calling `component-gate-runner`/`capability-scenario-verifier`
  directly, as `hotdocs build`); `D93` reversed the component half —
  `hotdocs generate`/`verify` independently runnable again,
  `check_readiness` back to a pure, read-only `provenance-checker`
  check (`R-TRACK-009`), `depends_on` back to `provenance-checker`,
  `write_attempt_record`/`last_requirement_failures` restored
  (`R-TRACK-004`/`007`/`008`). The capability half (check-then-run via
  `capability-scenario-verifier`) stands unreversed (`R-TRACK-010`).
- `D95`–`D126`: real cold-generation bootstrap, full round-by-round
  account in `BOOTSTRAP.md`. `last_requirement_failures`'s real
  `requirement_results` shape stated directly (`D95`); lazy
  dependency loading stated explicitly for both deps (`D98`); blast-
  radius-before-committing workflow MUST (`D99`); `AttemptRecord`'s
  in-memory shape stated (`D100`); dependency modules MUST resolve
  `repo_root`-relative, never file-location-relative or cached by
  name alone (`D111`, `R-TRACK-011`); dual dict-or-attribute access
  reading any dependency's return value (`D121`, `R-TRACK-012`,
  found only once accurate fakes first let this component's own code
  actually run); the `realizes` edge computed by scanning every
  component's own `component.md`, never a nonexistent reverse pointer
  on the capability's own file (`D122`, mirroring
  `capability-scenario-verifier`'s own internal convention).
- `D127`: landed at 5/7 (`mutation_score=1.0`, union across all
  generated-test criteria per `verifier-orchestrator`'s `D124` fix).
  Two known limitations, confirmed via direct sandbox inspection
  rather than accepted at face value: `AC-TRACK-009` — a failing
  hit's `not_ready_reasons` message doesn't distinguish which of
  `verification_report`/`license_scan`/`secret_scan` failed, nor
  name the specific failing requirement id, though `ready=False` and
  the component name are both correctly surfaced; `AC-TRACK-010` — a
  test-authoring fixture bug, not a candidate bug (both failing
  scenarios' `check_capability_provenance` fixture returns `hit=True`
  unconditionally, so the check-then-run short-circuit the candidate
  correctly takes means `run_capability_gates` and its injected
  failure are never reached).
