---
id: comp-generator
title: Generator
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-cache-manager, comp-llm-endpoint]
depends_on_guarantees: [G-CACHE-001]
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Generator

## Purpose

Calls a pinned model to produce `gen/<component>/` from a `SpecBundle` —
cold, with no prior code (unless the bundle carries `hint_code`),
exactly one candidate per invocation.

## Rationale

`hint_code` is a feature-branch-only exception. `G-CACHE-001`: see `D2`.

## Scope

**In scope:** constructing the model call from a `SpecBundle`, a model
identifier, and optional `retry_feedback` (`R-GEN-012`); checking the
cache first; in `cold` mode only, writing the result to
`gen/<component>/` and the cache (`R-GEN-016` — `hint` mode writes
neither); recording provenance.

**Out of scope:** any retry of its own; `generation-loop` retries
(`D310`).

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

All `generated-test`, with an injected mock model.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

`D35` onward: see the decisions, most recently `D304`, `D305` and
`D325`.

- `D343`: declared assets — R-GEN-015, R-GEN-021, `check_assets`,
  AC-GEN-024, AC-GEN-025; `generator@3.1.0`, `v12`.
