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
merging (`SPEC_GUIDELINES.md` §6 steps 5/7): the spec diff, changed
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

- **R-PACKET-001** — The packet MUST include the actual spec diff for this
  change — the primary thing a human reviews (D1/§6).
- **R-PACKET-002** — The packet MUST list which `R-id`s changed in this PR.
- **R-PACKET-003** — The packet MUST list which components were
  regenerated (from the blast radius `impact-analyzer` computed).
- **R-PACKET-004** — The packet MUST include verification results per
  regenerated component — the full pass/fail/skipped breakdown, not just an
  aggregate verdict.
- **R-PACKET-005** — License- and secret-scan results MUST appear as their
  own explicit section, even when both are clean — never folded into a
  generic results blob where a flag could be missed (D7/D12's "every flag
  strictly tracked and communicated").
- **R-PACKET-006** — Cache-hit status MUST be shown per component, visibly
  — never left for the reader to infer from the absence of other detail.
- **R-PACKET-007** — Any new or changed `sealed` or
  `gen/<component>/.overrides.json` declaration in this PR MUST appear as
  its own explicit section (principle 7/§8) — a declared exemption from the
  normal discipline is exactly the kind of thing a reviewer must see called
  out, not buried in a frontmatter diff.
- **R-PACKET-008** — "Residual risk" — non-blocking findings still worth a
  human's attention (a second-model verification failure, a size-cap
  warning nearing its hard-fail threshold) — MUST be its own section,
  distinct from pass/fail results.
- **R-PACKET-009** — A packet MUST be produced for every merge, including a
  fully clean one with no flags or warnings — never skipped, so the review
  habit stays consistent merge to merge rather than only appearing when
  something is wrong.
- **R-PACKET-010** — The packet MUST NOT include the generated code diff as
  primary content. This is deliberate, not an oversight: including a wall
  of generated-code diff would invite exactly the line-by-line code review
  principle 6 moved away from.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`ReviewPacket` schema).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
