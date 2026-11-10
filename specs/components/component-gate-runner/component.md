---
id: comp-component-gate-runner
title: Component Gate Runner
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-checker, comp-spec-bundle-assembler, comp-generator, comp-verifier-orchestrator, comp-license-scanner, comp-secret-scanner, comp-provenance-writer, comp-provenance-tracker, comp-test-author, comp-llm-endpoint]
realizes: [P-ZERO-EDIT, P-COMPLIANCE-GATE]
model_pin: claude-sonnet-5
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

Extracted from the since-removed `merge-orchestrator` (`D76`), then made
a developer-invoked command in its own right (`D86`, `D93`): generating
code is a deliberate, potentially expensive action a developer triggers
by name, distinct from `hotdocs verify`'s read-only check. `R-SIZE-002`
fires here (`fan_out` crowding `component_doc_words`) and is accepted:
wiring its own dependencies is genuinely this component's job.

## Scope

**In scope:** obtaining the canonical provenance key and short-
circuiting on a passing hit (`R-GATE-001`); on a miss, assembling,
generating once (cold mode), and verifying with its own `test_author`
and `judge` closures (`R-GATE-002`, `R-GATE-003`, `R-GATE-010`);
reporting a block and why (`R-GATE-004`); running both scans
(`R-GATE-005`); recording the attempt and, when a candidate was
produced, its provenance (`R-GATE-008`, `R-GATE-006`); routing a sealed
component straight to re-verification and recording its sealed
provenance (`R-GATE-007`); and the
`hotdocs generate` CLI (`R-GATE-009`).

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

See `acceptance/`. All `kind: generated-test`: every dependency is
faked under `gen/<slug>/` and the tests assert on call order,
arguments, and the returned `ComponentPipelineResult`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft (`D76`), extracted from `merge-orchestrator`.
- `D86`–`D93`: became the developer-invoked `hotdocs generate`, wiring
  its own closures and writing the attempt record via
  `provenance-tracker`.
- `D166`: rewritten before its first build — the canonical provenance
  key (`D163`), only a passing hit short-circuits, `blocked`/
  `block_reason` in the result, the exact dependency call list, the
  judge contract (`R-GATE-010`), CLI coverage (`R-GATE-009`).
  Cold-generated and landed at 13/13, `mutation_score` 0.88.
- `D170`: a sealed component now ends with a sealed provenance
  manifest written through `provenance-writer` (`R-GATE-007`);
  sealedness comes from `provenance-checker`'s `current_sealed_key`.
  Regenerated and landed at 13/13, `mutation_score` 0.94.
