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

The assist agent `notes/metrics.md` already assumes.

## Scope

**In scope:** running the cheap, deterministic checks first (lint, blast
radius, `spec-reviewer`'s deterministic criterion check for each
affected component); producing a judgment-based completeness assessment
and a corpus-wide redundancy/overlap check.

**Out of scope:** gating anything (R-ASSIST-006); re-deciding anything a
ratified spec already declares — this component may *suggest* a spec
change before ratification; it has no standing to override one after.

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

`D28`, `D155`, `D156`, `D157`, `D160`, `D201`, `D199`, `D301`.
