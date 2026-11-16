---
id: comp-spec-completeness-assistant
title: Spec Completeness Assistant
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter, comp-impact-analyzer, comp-spec-reviewer, comp-llm-endpoint]
realizes: [P-AMBIGUITY-GATE]
model_pin: claude-opus-5-5
sealed: false
---

# Spec Completeness Assistant

## Purpose

Helps a developer land a *complete* spec change on a feature branch —
dependencies updated, no logical discrepancies, no redundancies — by
checking each affected component's criteria from their test authors'
view and judging the change against the criteria that cover it,
**before** a change is even submitted to the real merge pipeline.

## Rationale

The assist agent the original brainstorm describes but never names. This is the component
`notes/metrics.md` already assumes exists (its "Completeness-agent
confidence" and "Assist-agent acceptance rate" metrics predate this
spec) but that, until now, had never actually been specced.

## Scope

**In scope:** running the cheap, deterministic checks first (lint, blast
radius, `spec-reviewer`'s deterministic criterion check for each
affected component); producing a judgment-based completeness assessment
and a corpus-wide redundancy/overlap check.

**Out of scope, and load-bearing, not incidental:** gating anything. This
component's output is advisory only — it is never read by
`provenance-tracker`'s own checks or any other component's `depends_on`,
and it has no mechanism to block a merge. The actual gates
(`spec-linter` at hard-fail severity, `verifier-orchestrator`, the
compliance scans) are the only things that can do that; this component
exists entirely on the feature-branch side of the cold-vs-hint split,
never the merge side. Also out of scope: **re-deciding anything a ratified
spec already declares** — same boundary `verifier-orchestrator`/
`test-author` observe for a criterion's `kind:`. This component may
*suggest* a spec change before ratification; it has no standing to override
one after.

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

Mixed `kind`, and deliberately the opposite mix from most of this corpus:
every criterion is a `generated-test` except R-ASSIST-004/005 — this
component's actual reason to exist — which are `llm-judge`. Unlike every coordination component specced so far
(`verifier-orchestrator`, `merge-orchestrator`), this one's core value
genuinely *is* judgment, not dispatch around it — a useful contrast case
against the corpus's usual "prefer compiled" guidance rather than
another confirmation of it.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
- `D28`: defined `redundancy_flags`' populated-entry shape
  (`{new_requirement, overlaps_with, rationale}`, `R-ASSIST-005`).
- `D155`–`D157`: hard-fail lint short-circuits; the dependency call
  order and signature are pinned; no model means no model call at all.
- `D160`: `R-ASSIST-009` covers the CLI; `R-ASSIST-010` pins the
  model-call response contract. Cold-generated and landed
  (`mutation_score` 0.81).
- `D201`: `R-ASSIST-011` covers the tool-root fallback (`D199`);
  dependencies are flat modules; more response-parsing cases.
- `D301`: previews come from `spec-reviewer`, not `generator`; lint
  halts only on a failure inside the change; the completeness prompt
  carries the covering criteria; redundancy is checked corpus-wide from
  deterministic candidates; a model makes lint run its glossary judge.
