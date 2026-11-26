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

Runs one component through its gauntlet — provenance check, generation
on a miss, verification, compliance scanning, provenance write — giving
one `ComponentPipelineResult`. A developer invokes it as `hotdocs
generate <component-id>`, before `hotdocs verify` and committing.

## Rationale

See `D76`, `D86`, `D93`.

## Scope

**In scope:** the provenance check and its short circuit; on a miss,
`generation-loop`'s attempts, both scans, attempt records and
provenance; a sealed component's re-verification; the `hotdocs
generate` CLI.

**Out of scope:** merge readiness (`provenance-tracker`'s `hotdocs
verify`); ordering `generate` calls across components
(`R-ASSEMBLE-011`).

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

`D76`, `D86`–`D93`, `D166`, `D170`, `D314`, `D345`, `D359`, `D370`,
`D371`.
