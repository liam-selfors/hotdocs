---
id: comp-decision-drift-detector
title: Decision Drift Detector
status: draft
owners: [pipeline-team]
depends_on: [comp-graph-query-engine]
realizes: [P-DECISION-INTEGRITY]
model_pin: claude-opus-5-5
sealed: false
---

# Decision Drift Detector

## Purpose

For every live spec file's `D<N>` citation, flags one whose cited
decision has since been superseded by a decision ratified after the
citing file's own last-modified commit — a candidate for staleness
review, never a verdict. Also answers the forward-looking question:
before altering or superseding a decision, what would be affected.

## Scope

**In scope:** resolving every `D<N>` citation in every live (non-
decision) spec file, the same citation shape `R-CITE-001` already
validates for existence; for each, querying `graph-query-engine`'s
`edges` for whether it has been superseded; for a superseded
citation, comparing the citing file's own last commit touching it
against the superseding decision's `last_ratified_commit`
(`decision_lineage`) via `git merge-base --is-ancestor`; reporting
every case where the file's commit predates the superseding
decision's ratification. Also: given any decision id, not
necessarily yet ratified, walking `edges` backward to find every
decision and live file that would be affected by altering it
(`R-DRIFT-003`).

**Out of scope:** judging whether a flagged file is actually wrong —
this surfaces candidates, never a correctness verdict. Never read by `provenance-tracker`'s own checks or any gate's
block decision — purely diagnostic, run on demand or periodically, not
part of the verification-gate workflow (`specs/architecture/
pipeline-decomposition.md`'s "Advisory tooling" table).

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

`D74`, `D75`, `D133`, `D134`, `D135`, `D130`, `D136`, `D137`.
