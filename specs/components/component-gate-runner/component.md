---
id: comp-component-gate-runner
title: Component Gate Runner
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-checker, comp-spec-bundle-assembler, comp-generator, comp-verifier-orchestrator, comp-license-scanner, comp-secret-scanner, comp-provenance-writer, comp-test-author, comp-llm-endpoint]
realizes: [P-ZERO-EDIT, P-COMPLIANCE-GATE]
sealed: false
---

# Component Gate Runner

## Purpose

Runs one component through its full per-component gauntlet — provenance
check, generation on a miss, verification dispatch, compliance scanning,
provenance write — producing one `ComponentPipelineResult`. Called
internally by `provenance-tracker`'s `hotdocs build` for every
component in scope — this component has no CLI of its own.

## Rationale

(`D76`.) Extracted out of `merge-orchestrator` once its
`component_doc_words` and `fan_out` crowded together — the same signal,
and the same kind of fix, `D14` already applied once for
`capability-scenario-verifier`. `D86` removed this component from
`merge-orchestrator`'s call graph entirely, reframing it as a
developer-invoked command rather than an internal sub-call; `D87`
removed `merge-orchestrator` itself, since checking what this component
already produced was its only remaining job, and that check didn't need
an orchestrating component to run it. `D92` folded this component's own
CLI into `provenance-tracker`'s combined `hotdocs build` — a developer
no longer invokes this component by name at all, and this component
writes its own attempt record directly rather than calling back into
`provenance-tracker`, specifically to avoid the dependency cycle that
would otherwise create.

**`R-LINT-022` fires on this component (`fan_out` crowding
`component_doc_words`)** — accepted, not a defect: `D86` gave this
component real new responsibility (its own wiring, its own
attempt-record write) that genuinely wasn't its job before, the honest
cost of no longer being called by an orchestrator that used to own
that wiring. No further split precedent exists yet for this specific
crowding; revisit if it gets worse, not preemptively.

## Scope

**In scope:** checking `provenance-checker` for a hit before doing
anything else (`R-GATE-001`); on a miss, calling `spec-bundle-assembler`
then `generator` (cold mode, sample index 0) to produce a candidate,
then `verifier-orchestrator` to check it — wiring the real
`test_author`/`judge` closures itself, capturing `model`/`seed`/
`llm_backend`/`repo_root` (`R-GATE-002`, `D86` — passed through from
whoever called `run_component_gates`, now always `provenance-tracker`);
treating a failed generation attempt as a block for this component,
distinguishing a `model_call_error` from a verification failure
(`R-GATE-003`, `R-GATE-004`); invoking `license-scanner` and
`secret-scanner` unconditionally regardless of provenance/generation
outcome (`R-GATE-005`); calling `provenance-writer` once
generation/verification and both scans have concluded (`R-GATE-006`);
routing a sealed component around all of the above entirely, straight
to an unconditional characterization-test re-run (`R-GATE-007`);
writing an `AttemptRecord` directly to `.hotdocs/attempts/` once its
own attempt concludes (`R-GATE-008`, `D92` — never a call into
`provenance-tracker`'s own code for this, to avoid a dependency cycle
now that `provenance-tracker` calls this component to trigger work).

**Out of scope:** deciding whether a merge may proceed — that is
`provenance-tracker`'s own `hotdocs build` (`D87`/`D92`), which calls
this component, never the reverse; sequencing multiple components'
gauntlets in dependency order across a multi-component change — that
is `provenance-tracker`'s own job now too (`R-TRACK-009`), resolving a
blast radius via `impact-analyzer` before calling this component once
per component in it.

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

All criteria are `kind: compiled` — tested by mocking every dependency
and asserting on call order/arguments/return shape, the same pattern
`merge-orchestrator` itself used for this exact logic before the
original split.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft (`D76`), extracted from `merge-orchestrator`'s
  `R-MERGE-003/004/005/006/008/009/015` (now `R-GATE-001` through
  `R-GATE-007`) and the corresponding ten acceptance criteria.
- `D86`: no longer called by `merge-orchestrator` — gets its own CLI
  (named `hotdocs prepare` at the time), wires its own
  `test_author`/`judge` closures (`R-GATE-002`, previously the
  caller's job), and takes over the per-component attempt record
  (`R-GATE-008`, previously `merge-orchestrator`'s `R-MERGE-021`).
- `D87`: `merge-orchestrator` removed entirely — nothing changes here
  beyond this component no longer having ever been called by it.
- `D88`: the per-component attempt record moves from `merge-tracker` to
  its renamed successor, `provenance-tracker` — superseded below.
- `D91`: CLI verb renamed `hotdocs generate` — superseded below.
- `D92`: this component's own CLI retired entirely — called internally
  by `provenance-tracker`'s `hotdocs build` instead. `R-GATE-008`
  rewritten to write `AttemptRecord`s directly rather than calling
  `provenance-tracker`'s `write_attempt_record`, breaking what would
  otherwise be a dependency cycle (`provenance-tracker` now depends on
  this component to trigger `hotdocs build`'s generation step).
  `depends_on` drops `provenance-tracker` entirely.
