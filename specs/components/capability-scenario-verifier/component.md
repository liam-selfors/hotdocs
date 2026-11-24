---
id: comp-capability-scenario-verifier
title: Capability Scenario Verifier
status: draft
owners: [pipeline-team]
depends_on: [comp-criterion-compiler, comp-test-author, comp-llm-endpoint]
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
model_pin: claude-opus-5-5
sealed: false
---

# Capability Scenario Verifier

## Purpose

Runs the capability scenarios of every product capability whose
`realizes`-set intersects a merge's blast radius, against the real,
fully assembled `gen/` output produced by that merge — the permanent,
cross-component backstop for behavioral risk no `interface/`-level
diffing can fully rule out by documentation alone. The cross-component analog
of `verifier-orchestrator`, with the same dispatch mechanisms.

## Rationale

Covers `interface/guarantees/` too (`D2`, `R-IMPACT-008`); extracted
from `merge-orchestrator` (`D14`).

## Scope

**In scope:** the capability-intersection lookup; dispatching each
scenario by its declared `kind` with the mechanisms `verifier-orchestrator`
established; one result per scenario, keyed by `P-id`; checking and
writing its own provenance for one capability, keyed on its realizing
components' actual content (`R-SCENARIO-004`), for `hotdocs verify`.

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

Every criterion is `kind: generated-test` (`D43`): dispatch-and-
aggregate logic, tested with fake dependencies under a temporary
`repo_root`, asserting on call arguments and results.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

`D14`, `D23`, `D59`–`D61`, `D68`, `D87`–`D93`, `D174`, `D175`, `D198`,
`D344`, `D345`, `D370`.
