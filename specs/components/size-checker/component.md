---
id: comp-size-checker
title: Size Checker
status: draft
owners: [pipeline-team]
depends_on: [comp-corpus-loader]
realizes: [P-AMBIGUITY-GATE]
model_pin: claude-sonnet-5
sealed: false
---

# Size Checker

## Purpose

Measures each component of a spec corpus against the size caps of
`SPEC_GUIDELINES.md` §4, per component, per unit file and per `Purpose`
section, and reports each cap exceeded, and each component crowding
several caps at once, as a finding for the linter's report.

## Rationale

Split out of `spec-linter` with its size rules (`D242`).

## Scope

**In scope:** the rules in `requirements/`. "The linter" in a
requirement means this component's `check`.

**Out of scope:** the report, the CLI and every other rule, which stay
with `spec-linter`.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

None.

## Acceptance criteria

See `acceptance/`. All `generated-test`, over small corpora written to a
temporary `repo_root`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- `D242`: split out of `spec-linter`, with `R-LINT-012`, `022`, `023` and
  `025` renumbered `R-SIZE-001`–`004`.
