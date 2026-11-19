---
id: comp-component-gate-runner
title: Component Gate Runner
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-checker, comp-spec-bundle-assembler, comp-generation-loop, comp-verifier-orchestrator, comp-license-scanner, comp-secret-scanner, comp-provenance-writer, comp-provenance-tracker]
realizes: [P-ZERO-EDIT, P-COMPLIANCE-GATE]
model_pin: claude-opus-5-5
sealed: false
---

# Component Gate Runner

## Purpose

Runs one component through its full per-component gauntlet — provenance
check, generation on a miss, verification dispatch, compliance scanning,
provenance write — producing one `ComponentPipelineResult`. A developer
invokes this directly (`hotdocs generate <component-id>`) to produce a
component's `gen/` content and provenance explicitly, before checking
`hotdocs verify` and committing.

## Rationale

Extracted from `merge-orchestrator` (`D76`), then a developer-invoked
command (`D86`, `D93`): generating is a deliberate, costly action,
distinct from `hotdocs verify`'s read-only check. `R-SIZE-002` is
accepted: wiring its own dependencies is this component's job.

## Scope

**In scope:** obtaining the canonical provenance key and short-
circuiting on a passing hit (`R-GATE-001`); re-verifying on an
`environment differs` miss (`R-GATE-011`); on a miss, assembling and
running `generation-loop`'s bounded attempts (`R-GATE-002`,
`R-GATE-003`); reporting a block and why (`R-GATE-004`); running both scans
(`R-GATE-005`); recording each attempt and, when a candidate was
produced, its provenance (`R-GATE-008`, `R-GATE-006`); routing a sealed
component straight to re-verification and recording its sealed
provenance (`R-GATE-007`); and the
`hotdocs generate` CLI, with attempt and mode defaults from
`hotdocs.toml` (`R-GATE-009`, `R-GATE-010`).

**Out of scope:** deciding merge readiness — `provenance-tracker`'s
`hotdocs verify`, reading what this component wrote; sequencing
`generate` calls across a multi-component change in `depends_on` order —
the developer's own discipline (`R-ASSEMBLE-011`).

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`, all `kind: generated-test`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft (`D76`), extracted from `merge-orchestrator`.
- `D86`–`D93`: became the developer-invoked `hotdocs generate`.
- `D166`: the canonical provenance key (`D163`), only a passing hit
  short-circuits, `blocked`/`block_reason`, CLI coverage (`R-GATE-009`).
- `D170`: a sealed component records sealed provenance (`R-GATE-007`).
  Landed at 13/13, `mutation_score` 0.94.
- `D314`: generation goes through `generation-loop` (`D310`); one
  attempt record per attempt, counted from `.hotdocs/attempts/<component_id>/`;
  `--max-attempts`, `--mode` and `hotdocs.toml` defaults.
- `D345`: an `environment differs` miss first re-verifies the committed
  code without a model and, when it passes, re-records provenance
  (`R-GATE-011`, result `reverified`).
