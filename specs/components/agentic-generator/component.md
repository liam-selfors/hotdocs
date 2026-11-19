---
id: comp-agentic-generator
title: Agentic Generator
status: draft
owners: [pipeline-team]
depends_on: [comp-generator, comp-llm-tool-endpoint]
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Agentic Generator

## Purpose

Generates a component's code the way a developer would: the model reads
its spec bundle, writes the module, imports it, writes and runs its own
tests, and revises, inside a sandbox it cannot leave, until it calls
`finish`. Returns the same `GenerationResult` single-shot generation
does, so the verifier and the gate treat both alike.

## Scope

**In scope:** building the sandbox from the bundle; the tools and their
path rules; running the model's code under the OS sandbox; turning
`work/` into a `GenerationResult` and writing it to `gen/<component>/`.

**Out of scope:** verifying the candidate; caching; retrying; the tool
loop's wire formats (`llm-tool-endpoint`).

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

`generator`'s `GenerationResult`.

## Acceptance criteria

See `acceptance/`.

All are `kind: generated-test`, with a `llm-tool-endpoint` stand-in that
drives the tools from a script.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- `D309`: initial spec.
- `D343`: R-AGENT-001 environment check, R-AGENT-002 asset paths, R-AGENT-005 `check_assets`; AC-AGENT-010; `agent-v2`.
