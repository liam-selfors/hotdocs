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

See `D184`.

## Scope

**In scope:** the dispatcher, its verb table, and `help`/`--version`;
routing `init` to `hotdocs-init`.

**Out of scope:** what each verb does, including `init`; the `pyproject.toml`
and the entry module in `tools/`, hand-authored.

**Loose coupling, on purpose.** The only dependency is `llm-endpoint`, for
the configured model. Verb targets are reached by loading their `main` (`init`'s `run`) by
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

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

`D184`, `D185`, `D346`, `D348`, `D360`, `D363`, `D364`.
