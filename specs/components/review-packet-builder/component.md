---
id: comp-review-packet-builder
title: Review Packet Builder
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-writer]
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

**In scope:** formatting already-computed results — verification,
license/secret scan, provenance-hit status — into one reviewable
document, read entirely from `provenance-writer`'s already-written manifests
(`R-PACKET-011`, D13), which already collected all of it; no live
dependency on `verifier-orchestrator`, `license-scanner`,
`secret-scanner`, or `cache-manager` is needed to do this.

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

All eleven criteria are `kind: compiled` — formatting already-computed
results is pure, deterministic logic.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
- `D29`: `cache_hit_status` renamed `provenance_hit_status`
  (`R-PACKET-006`); `R-PACKET-011`'s source list drops `cache-manager`,
  which this field never actually came from.
