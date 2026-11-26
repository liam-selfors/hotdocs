---
id: comp-llm-endpoint
title: LLM Endpoint
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
uses_var: [VAR-ANTHROPIC-API-KEY, VAR-OPENAI-API-KEY, VAR-GEMINI-API-KEY, VAR-HOTDOCS-CONFIG]
model_pin: claude-opus-5-5
sealed: false
---

# LLM Endpoint

## Purpose

A single, vendor-agnostic transport for every model call this pipeline
makes — `generator`, `test-author`, `spec-completeness-assistant`, and
the real `judge` callable `merge-orchestrator` wires into
`verifier-orchestrator`/`capability-scenario-verifier` all dispatch through
here instead of each independently knowing how to authenticate to, and
call, a specific vendor's API.

## Rationale

See `D18`.

## Scope

**In scope:** every rule in `requirements/`, for the six providers and
the setup helpers `hotdocs init` uses.

**Out of scope:** building or parsing any task's prompt, which each
caller owns, and retrying (`R-ENDPOINT-004`).

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

- `ollama` silently truncates a prompt longer than its server's context
  window unless `num_ctx` is passed; no default is set, since a safe
  value depends on the model and the machine (`D182`).

## Change log

`D18`, `D33`, `D34`, `D35`, `D52`, `D82`, `D180`, `D181`, `D182`, `D183`, `D209`, `D220`, `D221`, `D223`, `D224`, `D225`.
