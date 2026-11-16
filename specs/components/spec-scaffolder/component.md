---
id: comp-spec-scaffolder
title: Spec Scaffolder
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-DECISION-INTEGRITY]
model_pin: claude-opus-5-5
sealed: false
---

# Spec Scaffolder

## Purpose

Takes the mechanical work out of growing a specbase: allocating the next
decision id, writing a decision record's skeleton, ratifying it,
recording the commit that landed it, and laying out a new component's
directory. It writes structure and frontmatter only, never normative
content.

## Scope

**In scope:** `hotdocs decision new`, `decision ratify`,
`decision record-commit` and `component new`, and the library functions
behind them, all acting on files under a given `repo_root`.

**Out of scope:** writing a decision's reasoning or a component's
requirements and criteria; deciding whether a decision is right;
committing anything to git. `record-commit` only reads git history.

## Definitions

A **draft** decision record has `status: draft`; a **ratified** one has
`status: ratified` and a `last_ratified_commit`. The placeholder
`PENDING-COMMIT` stands for the commit not yet recorded.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

None.

## Acceptance criteria

See `acceptance/`.

All criteria are `kind: generated-test`: each builds a temporary
`repo_root` on disk, and the commit-recording criterion a real git
repository, which the compiled step grammar cannot express.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- `D299`: initial spec.
