---
id: comp-capability-scenario-verifier
title: Capability Scenario Verifier
status: draft
owners: [pipeline-team]
depends_on: [comp-criterion-compiler, comp-test-author]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
sealed: false
---

# Capability Scenario Verifier

## Purpose

Runs the capability scenarios of every product capability whose
`realizes`-set intersects a merge's blast radius, against the real,
fully assembled `gen/` output produced by that merge — the permanent,
cross-component backstop for behavioral risk no `interface/`-level
diffing can fully rule out by documentation alone. Structurally, the
cross-component analog of what `verifier-orchestrator` already does
per-component: same dispatch mechanisms
(`criterion-compiler`/`test_author`/`judge`), one scope level up.

## Rationale

Covers `interface/guarantees/` too (D16) — the same reasoning
`R-IMPACT-008` already states. Extracted from `merge-orchestrator` (D25)
once that component's fan-out and spec-bundle-word caps crowded their
ceilings simultaneously — a signal, D25 concluded, that this dispatch
logic had its own identity, not merely convenient placement. Renamed
from "golden-scenario-verifier" (`D36`): "golden" named nothing about
what this actually is — a capability-level, end-to-end analog of a
component's own acceptance criteria, exactly mirroring "Acceptance
Criterion" one scope level up.

## Scope

**In scope:** the capability-intersection lookup (which `P-id`s to run);
dispatching each capability scenario by its declared `kind` using
exactly the mechanisms `verifier-orchestrator` already established — no
new dispatch machinery; producing one result per scenario, keyed by
`P-id`.

**Out of scope:** deciding whether a failure here blocks the merge
(`merge-orchestrator`'s `R-MERGE-011` job, unchanged by this extraction);
authoring capability scenarios themselves (a product-capability spec
author's job, same as any other acceptance criterion); re-deciding a
criterion's declared `kind` (fixed at spec-authoring time, same
invariant `verifier-orchestrator` already honors).

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

All four criteria are `kind: generated-test` (`D59`) — dispatch-and-
aggregate logic, tested by mocking the dispatch mechanisms and
asserting on call arguments/results, the same pattern
`verifier-orchestrator` already established for coordination logic;
none are actually written in the step-phrase grammar, so
`kind: compiled` would not describe how they're really verified.

## Non-functional constraints

See `constraints.md`.

## Open questions

None — extracted whole from `merge-orchestrator`'s already-resolved
`R-MERGE-014`/`R-MERGE-020`, not a fresh design.

## Change log

- Initial draft (extracted from `merge-orchestrator`, D25).
- Renamed from `golden-scenario-verifier`; `CapabilityScenarioReport`
  moved to per-scenario granularity with a shared `rationale` field
  (`D36`).
- `D75`/`D76`/`D77`/`D78`: first real implementation, via three real
  `generate()` calls. `D75` added `criterion-compiler`'s
  `compile_criterion` primitive and fixed the real capability-scenario
  location; `D76` fixed sealed-dependency visibility in
  `spec-bundle-assembler`; `D77` clarified that `realizes` edges are
  per-component. A third retry, with all three fixes in place, passed
  all 3 `AC-SCENARIO-*` criteria. `gen/capability-scenario-verifier/
  capability_scenario_verifier.py` is now that candidate. See
  `verification/capability-scenario-verifier/BOOTSTRAP.md`.
- `D84`: documented, not changed — the real candidate always
  dispatches `generated-test` scenarios fresh, with no cache-file
  pre-check (`R-SCENARIO-001`), found undocumented by a pre-generation
  audit. Not a real inefficiency (`test_author`'s own cache-manager
  check already avoids a redundant model call); confirmed by a new
  `AC-SCENARIO-004`.
