---
id: comp-citation-checker
title: Citation Checker
status: draft
owners: [pipeline-team]
depends_on: [comp-corpus-loader]
realizes: [P-AMBIGUITY-GATE]
model_pin: claude-opus-5-5
sealed: false
---

# Citation Checker

## Purpose

Checks that every citation in a spec corpus resolves: decision numbers,
pointers to a section of another file, glossary citations, and the
`supersedes` and `builds_on` links between decision records. It reports
each one that does not as a finding for the linter's report.

## Rationale

Split out of `spec-linter` with its citation rules (`D242`).

## Scope

**In scope:** the rules in `requirements/`. "The linter" in a
requirement means this component's `check`.

**Out of scope:** the report, the CLI and every other rule, which stay
with `spec-linter`.

## Definitions

A **live document** is every `Doc` in the corpus except decision records.
A citation of `D1`–`D14`, frozen at the baseline reset and never written
as files, always resolves.

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

- `D242`: split out of `spec-linter`, with `R-LINT-026`–`030` renumbered
  `R-CITE-001`–`005`.
