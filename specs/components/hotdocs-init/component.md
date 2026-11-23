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

A project needs a known layout and a working provider before anything else
runs. `init` once copied the tool into each project (`D184`); components
now fall back to the tool's own `gen/` (`D199`), so it copies nothing. It was first specified inside
`hotdocs-cli`, but one generated module covering both routing and setup was
too large for a single model response (`D185`).

## Scope

**In scope:** the project skeleton, the prerequisite report, the
provider step, and the `--example` project.

**Out of scope:** routing (`hotdocs-cli` calls this component's `run`);
installing anything (this component prints the command and never runs it).

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

None.

## Acceptance criteria

See `acceptance/`. All `kind: generated-test`: a temporary project directory
and a fake tool root.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- `D184`: initial design, inside `hotdocs-cli`. `D185`: split out.
- `D197`: seeds a sealed allowlist. `D199`: copies nothing from the tool;
  the allowlist starts empty.
- `D203`: the Python floor is 3.11. `D205`: `.hotdocs-tool.json` marks
  an initialised project.
- `main(argv)` alone is the `cli-conventions.md` entry, deriving the tool
  root; the injectable form, called by `hotdocs-cli`, is now `run`. (`D348`)
- `D360`: the version is read from the tool root's `pyproject.toml`; the
  next steps give the guide's path.
