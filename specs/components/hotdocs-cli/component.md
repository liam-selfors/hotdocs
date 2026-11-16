---
id: comp-hotdocs-cli
title: Hotdocs CLI
status: draft
owners: [pipeline-team]
depends_on: [comp-llm-endpoint]
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Hotdocs CLI

## Purpose

The single `hotdocs` command: routes `hotdocs <verb> ...` to the component
that implements the verb.

## Rationale

Every component had its own `main` and nothing routed to them, so there was
no `hotdocs` command (`D184`). The table of verbs, with each component's
argument contract, is data so a verb is one row and a generation never
guesses a contract.

## Scope

**In scope:** the dispatcher, its verb table, and `help`/`--version`;
routing `init` to `hotdocs-init`.

**Out of scope:** what each verb does, including `init`; the `pyproject.toml`
and the entry module in `tools/`, hand-authored.

**Loose coupling, on purpose.** The only dependency is `llm-endpoint`, for
the configured model. Verb targets are reached by loading their `main` by
path from the table, not through their Python APIs, so no verb can break
this component's interface.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`. All `kind: generated-test`: a temporary project and fake components that log their `argv`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- `D184`: initial design. `D185`: setup (`init`) split out to `hotdocs-init`.
