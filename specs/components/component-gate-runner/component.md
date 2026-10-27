---
id: comp-component-gate-runner
title: Component Gate Runner
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-checker, comp-spec-bundle-assembler, comp-generator, comp-verifier-orchestrator, comp-license-scanner, comp-secret-scanner, comp-provenance-writer]
realizes: [P-ZERO-EDIT, P-COMPLIANCE-GATE]
sealed: false
---

# Component Gate Runner

## Purpose

Runs one impacted, non-sealed component through its full per-component
gauntlet — provenance check, generation on a miss, verification dispatch,
compliance scanning, provenance write — and returns one
`ComponentPipelineResult`. `merge-orchestrator` calls this once per
impacted component instead of inlining the gauntlet itself.

## Rationale

(`D76`.) Extracted out of `merge-orchestrator` the second time its
`component_doc_words` and `fan_out` crowded together — the same signal,
and the same kind of fix, `D14` already applied once for
`capability-scenario-verifier`. Every downstream call this component
makes (`provenance-checker`, `spec-bundle-assembler`, `generator`,
`verifier-orchestrator`, `license-scanner`, `secret-scanner`,
`provenance-writer`) was previously a direct `merge-orchestrator`
dependency used for nothing but this gauntlet, so none of them need to
remain a direct `merge-orchestrator` dependency after the split.

## Scope

**In scope:** checking `provenance-checker` for a hit before doing
anything else (`R-GATE-001`); on a miss, calling `spec-bundle-assembler`
then `generator` (cold mode, sample index 0) to produce a candidate,
then `verifier-orchestrator` to check it, accepting already-wired real
`test_author`/`judge` callables as parameters rather than wiring them
itself (`R-GATE-002`); treating a failed generation attempt as a block
for this component, distinguishing a `model_call_error` from a
verification failure (`R-GATE-003`, `R-GATE-004`); invoking
`license-scanner` and `secret-scanner` unconditionally regardless of
provenance/generation outcome (`R-GATE-005`); calling
`provenance-writer` once generation/verification and both scans have
concluded (`R-GATE-006`); routing a sealed component around all of the
above entirely (`R-GATE-007`).

**Out of scope:** deciding *when* to call this component, or for which
components, across a blast radius (`merge-orchestrator`'s own
scheduling, `R-MERGE-017`/`023`); wiring the real `test_author`/`judge`
closures (`merge-orchestrator`'s job, `R-MERGE-004`/`014` unchanged —
it already independently needs the same closures for its own
`capability-scenario-verifier` call, so there is exactly one wiring
site, not two); the overall merge block decision, atomic commit, review
packet, or merge-tracker reporting (all still `merge-orchestrator`).

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

All seven criteria are `kind: compiled` — tested by mocking every
dependency and asserting on call order/arguments/return shape, the same
pattern `merge-orchestrator` itself used for this exact logic before the
split.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft (`D76`), extracted from `merge-orchestrator`'s
  `R-MERGE-003/004/005/006/008/009/015` (now `R-GATE-001` through
  `R-GATE-007`) and the corresponding ten acceptance criteria.
