---
id: comp-spec-completeness-assistant
title: Spec Completeness Assistant
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter, comp-impact-analyzer, comp-spec-bundle-assembler, comp-generator]
realizes: [P-AMBIGUITY-GATE]
uses_var: [VAR-ANTHROPIC-API-KEY]
model_pin: claude-sonnet-5
sealed: false
---

# Spec Completeness Assistant

## Purpose

The assist agent D1 describes but never names: helps a developer land a
*complete* spec change on a feature branch — dependencies updated, no
logical discrepancies, no redundancies — using hint-mode previews to
evaluate completeness **before** a change is even submitted to the real
merge pipeline. This is the component `notes/metrics.md` already assumes
exists (its "Completeness-agent confidence" and "Assist-agent acceptance
rate" metrics predate this spec) but that, until now, had never actually
been specced.

## Scope

**In scope:** running the cheap, deterministic checks first (lint, blast
radius); producing a hint-mode preview; producing a judgment-based
completeness assessment and a redundancy/overlap check.

**Out of scope, and load-bearing, not incidental:** gating anything. This
component's output is advisory only — it is never in `merge-orchestrator`'s
dependency list, and it has no mechanism to block a merge. The actual gates
(`spec-linter` at hard-fail severity, `verifier-orchestrator`, the
compliance scans) are the only things that can do that; this component
exists entirely on the feature-branch side of D1's cold-vs-hint split,
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
R-ASSIST-001–003 and R-ASSIST-006 are `compiled` (dispatch, path/data
checks), but R-ASSIST-004/005 — this component's actual reason to exist —
are `llm-judge`. Unlike every coordination component specced so far
(`verifier-orchestrator`, `merge-orchestrator`), this one's core value
genuinely *is* judgment, not dispatch around it — a useful contrast case
for D5's guidance rather than
another confirmation of "prefer compiled."

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
