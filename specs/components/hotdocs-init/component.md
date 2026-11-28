---
id: comp-hotdocs-init
title: Hotdocs Init
status: draft
owners: [pipeline-team]
depends_on: [comp-llm-endpoint]
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Hotdocs Init

## Purpose

Sets up a new project for the tool: the directory skeleton, a check of what the machine still needs, and the choice and test of a
language-model provider.

## Rationale

See `D184`, `D185`, `D199`.

## Scope

**In scope:** the project skeleton, the prerequisite report, the
provider step, and the `--example` project.

**Out of scope:** routing (`hotdocs-cli` calls this component's `run`);
installing anything.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

None.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

`D184`, `D185`, `D197`, `D199`, `D203`, `D205`, `D348`, `D360`, `D365`.
