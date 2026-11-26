---
id: comp-review-packet-builder
title: Review Packet Builder
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-tracker]
realizes: [P-ZERO-EDIT, P-COMPLIANCE-GATE]
model_pin: claude-opus-5-5
sealed: false
---

# Review Packet Builder

## Purpose

Assembles the human-readable summary a reviewer actually reads before
merging (`SPEC_GUIDELINES.md` §6 steps 4/6): the spec diff, changed
requirements, regenerated components, verification results, flags, and
residual risk — never the generated code itself.

## Scope

**In scope:** formatting already-computed results — verification,
license/secret scan, provenance-hit status, and capability-scenario
results — into one reviewable document, read entirely from
`provenance-tracker`'s own `check_readiness` (`R-PACKET-011`, `D90`).

**Out of scope:** computing any of those results itself; deciding whether
the merge is allowed (gates already decided that; this component reports,
it doesn't gate).

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

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

`D29`, `D90`, `D140`, `D141`, `D145`, `D150`, `D153`, `D147`, `D148`, `D149`, `D151`, `D152`, `D201`, `D199`, `D371`.
