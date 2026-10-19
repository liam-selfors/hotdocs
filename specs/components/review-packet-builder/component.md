---
id: comp-review-packet-builder
title: Review Packet Builder
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-writer, comp-verifier-orchestrator, comp-license-scanner, comp-secret-scanner, comp-cache-manager]
realizes: [P-ZERO-EDIT, P-COMPLIANCE-GATE]
sealed: false
---

# Review Packet Builder

## Purpose

Assembles the human-readable summary a reviewer actually reads before
merging (`SPEC_GUIDELINES.md` §6 steps 4/6): the spec diff, changed
requirements, regenerated components, verification results, flags, and
residual risk — never the generated code itself.

## Scope

**In scope:** formatting already-computed results from `provenance-writer`,
`verifier-orchestrator`, `license-scanner`, and `secret-scanner` into one
reviewable document.

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

All ten criteria are `kind: compiled` — formatting already-computed results
is pure, deterministic logic. A seventh component in this corpus whose
entire acceptance set is `compiled`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
