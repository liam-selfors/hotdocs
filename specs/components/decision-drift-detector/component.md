---
id: comp-decision-drift-detector
title: Decision Drift Detector
status: draft
owners: [pipeline-team]
depends_on: [comp-graph-query-engine]
realizes: [P-DECISION-INTEGRITY]
sealed: false
---

# Decision Drift Detector

## Purpose

For every live spec file's `D<N>` citation, flags one whose cited
decision has since been superseded by a decision ratified after the
citing file's own last-modified commit — a candidate for staleness
review, never a verdict.

## Scope

**In scope:** resolving every `D<N>` citation in every live (non-
decision) spec file, the same citation shape `R-LINT-026` already
validates for existence; for each, querying `graph-query-engine`'s
`decision_lineage` for whether it has been superseded; for a
superseded citation, comparing the citing file's own last commit
touching it against the superseding decision's `last_ratified_commit`
via `git merge-base --is-ancestor`; reporting every case where the
file's commit is an ancestor of (predates) the superseding decision's
ratification.

**Out of scope:** judging whether a flagged file is actually wrong —
this surfaces candidates, never a correctness verdict, the same
posture `spec-completeness-assistant` takes for its own judgment
calls. Never wired into `merge-orchestrator`'s block decision — purely
diagnostic, run on demand or periodically, not part of the merge
pipeline (`specs/architecture/pipeline-decomposition.md`'s "Advisory
tooling" table).

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

Both criteria are `kind: compiled` — deterministic git/graph queries,
no model or judgment involved, tested against a synthetic git repo
built inside the test itself (real commits, real ancestry), not a
mock — the actual behavior being checked is git ancestry, which a
mock can't exercise meaningfully.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft (`D89`).
