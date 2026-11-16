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
this surfaces candidates, never a correctness verdict, the same
posture `spec-completeness-assistant` takes for its own judgment
calls. Never read by `provenance-tracker`'s own checks or any gate's
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

All three criteria are `kind: generated-test` (`D133`) — each needs a
synthetic git repo built inside the test itself (real commits, real
ancestry), not a mock, since the actual behavior being checked is git
ancestry; `criterion-compiler`'s fixed step grammar has no step form
for constructing arbitrary commits, only literal-value fixtures and a
single function call, so this setup is unreachable through `kind:
compiled` despite the deterministic, judgment-free logic it exercises.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft (`D75`).
- `D74`/`D75`: `R-DRIFT-001` rewired onto `edges` (decisions became
  graph-native, `decision_lineage` narrowed); `R-DRIFT-003` added
  pre-ratification impact analysis.
- `D133`: real cold-generation, first attempt. All three criteria
  were mis-declared `kind: compiled`; `criterion-compiler`'s fixed
  step grammar cannot express building a synthetic git repo with real
  commits, which these criteria's own tests genuinely need. Changed
  to `kind: generated-test`.
- `D134`: second attempt. Citation extraction MUST use the literal
  `\bD\d+\b` pattern, not a backtick-requiring one (`R-DRIFT-001`
  amended); `graph-query-engine` MUST resolve relative to `repo_root`,
  never this component's own `__file__` location — the `R-TRACK-011`/
  `R-VERIFY-013` bug class recurring a third time (`R-DRIFT-004`).
- `D135`: third attempt. A real DuckDB extension-registry conflict
  (bare `INSTALL yaml` vs. the required `FROM community`) traced to a
  `graph-query-engine` documentation gap, fixed there, not here.
- `D136`: fourth attempt, all four behaviorally passed. `main()`'s
  CLI entry point (`interface/cli.md`) had no requirement or
  acceptance criterion at all, same shape as `provenance-writer`'s
  own `D130` — caught by mutation score (`R-DRIFT-005`,
  `AC-DRIFT-005`).
- `D137`: mutation score oscillated `0.58`–`1.0` across seeds; nine
  consistently surviving mutants traced to three under-specified
  scenarios (multi-superseder tie-break, no-`--repo-root` CLI
  default, invalid `--format`) added directly to `AC-DRIFT-001`/
  `AC-DRIFT-005`, no new requirement needed. Landed 5/5,
  `mutation_score=0.84`. Full account in `BOOTSTRAP.md`.
