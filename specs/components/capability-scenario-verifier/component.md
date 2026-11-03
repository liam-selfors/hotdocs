---
id: comp-capability-scenario-verifier
title: Capability Scenario Verifier
status: draft
owners: [pipeline-team]
depends_on: [comp-criterion-compiler, comp-test-author, comp-llm-endpoint]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
model_pin: claude-sonnet-5
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

Covers `interface/guarantees/` too (`D2`), for the reason `R-IMPACT-008`
states. Extracted from `merge-orchestrator` (`D14`) when that
component's fan-out and word caps crowded together. Renamed from
"golden-scenario-verifier": a capability-level analog of a component's
acceptance criteria, one scope level up.

## Scope

**In scope:** the capability-intersection lookup; dispatching each
scenario by its declared `kind` with the mechanisms `verifier-orchestrator`
established; one result per scenario, keyed by `P-id`; checking and
writing its own provenance for one capability, keyed on its realizing
components' actual content (`R-SCENARIO-004`) — called internally by
`provenance-tracker`'s `hotdocs verify`, never by a developer directly.

**Out of scope:** deciding whether a merge proceeds
(`provenance-tracker`'s readiness check does, `D88`); authoring
capability scenarios, a product-spec author's job; re-deciding a
scenario's `kind`, fixed at authoring time.

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

Every criterion is `kind: generated-test` (`D43`) — dispatch-and-
aggregate logic, tested with fake dependencies placed under a temporary
`repo_root` and asserting on call arguments and results, the pattern
`verifier-orchestrator` established for coordination logic. None is
written in the step-phrase grammar, so `kind: compiled` would not
describe how they are really verified.

## Non-functional constraints

See `constraints.md`.

## Open questions

None — extracted whole from `merge-orchestrator`'s already-resolved
`R-MERGE-014`/`R-MERGE-020`, not a fresh design.

## Change log

- Initial draft (extracted from `merge-orchestrator`, `D14`); renamed
  from `golden-scenario-verifier`; per-scenario report granularity (`D23`).
- `D59`–`D61`, `D68`: first real implementation; where scenarios live;
  `realizes` is per-component; `generated-test` always dispatched fresh.
- `D87`–`D93`: own provenance mechanism (`R-SCENARIO-004`), keyed on
  realizing components' actual content; no CLI; wires its own closures.
- `D174`: specified `check_capability_provenance`/`run_capability_gates`,
  never built until now. Scenarios are now actually run
  (`R-SCENARIO-005`; they used to pass once a test was merely produced),
  the key also covers the capability's own scenarios, the closures are
  specified (`R-SCENARIO-007`/`008`), and `interface/cli.md` — which
  said only "None" — is removed.
- `D175`: cold-generated and landed at 12/12, `mutation_score` 0.84. A
  `compiled` capability scenario cannot pass with `surface=None`.
