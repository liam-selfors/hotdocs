---
id: comp-review-packet-builder
title: Review Packet Builder
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-tracker]
realizes: [P-ZERO-EDIT, P-COMPLIANCE-GATE]
model_pin: claude-sonnet-5
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
`provenance-tracker`'s own `check_readiness` (`R-PACKET-011`, `D90`),
which already assembles all of it, component and capability alike; no
live dependency on `verifier-orchestrator`, `license-scanner`,
`secret-scanner`, `provenance-checker`, or `capability-scenario-verifier`
is needed to do this.

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

All twelve criteria are `kind: generated-test` — real git-history
scenarios (sealed/override transitions, CLI invocation, markdown
rendering) need arbitrary setup code no fixed step grammar can
express, not purely literal-value fixtures.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
- `D29`: `cache_hit_status` renamed `provenance_hit_status`
  (`R-PACKET-006`); `R-PACKET-011`'s source list drops `cache-manager`,
  which this field never actually came from.
- `D90`: `depends_on` swaps `provenance-writer` for `provenance-tracker`
  directly — reads its `check_readiness` aggregate instead of the
  `component_provenance` view over `provenance-writer`'s manifests.
  `ReviewPacket` gains `capability_scenarios` (`R-PACKET-011`), closing
  a real gap: the old `merge-orchestrator`'s own spec always assumed
  this packet carried capability-scenario results, but nothing in this
  component's own requirements ever actually added them.
- `D140`/`141`: `spec_diff`'s base ref (merge-base with default
  branch), `changed_ids`'s own semantics (never git-derived),
  `residual_risk`/`compliance_flags` entry shapes, and
  `regenerated_components`'s source (`provenance-tracker`'s own
  `components` map, never `impact-analyzer` directly) all pinned down
  with worked examples — real test-authoring rounds kept guessing
  differently each time without them.
- `D145`/`150`/`153`: `R-PACKET-012`, the CLI entry point
  (`main`/`cli.md`) had zero coverage; its markdown rendering's own
  structure is now normative — flat lines or bold labels, never a
  nested per-entry sub-heading, after that ambiguity repeatedly broke
  a generated test's own section-boundary parse.
- `D147`/`148`/`149`/`151`/`152`: `sealed`-transition detection
  landed on comparing each file against its own first commit in
  `HEAD`'s history, independent of `R-PACKET-001`'s own PR diff-base
  — three earlier, each-plausible-looking approaches (diff-status
  letter, PR-diff-base existence, "doesn't exist implies unsealed")
  each broke a different real git-history shape before this one held.
- Landed (`D151`'s own retry, `mutation_score=0.82`): swapped in.
