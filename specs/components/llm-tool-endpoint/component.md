---
id: comp-llm-tool-endpoint
title: LLM Tool Endpoint
status: draft
owners: [pipeline-team]
depends_on: [comp-llm-endpoint]
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# LLM Tool Endpoint

## Purpose

Runs a multi-turn conversation in which the model calls tools the caller
defines, until the model stops or a budget runs out, over any provider
that supports tool use. The caller supplies the tools and one function
that executes a call; this component owns the wire format, the loop and
its bounds.

## Scope

**In scope:** the `anthropic`, `openai` and `openai-compatible` HTTP
tool loops; the `claude-cli` loop through a stdio MCP server it starts;
turn, tool-call and wall-clock budgets; the transcript.

**Out of scope:** what a tool does (the caller's `execute`); retrying a
failed call; single-shot completion (`llm-endpoint`); `gemini` and
`ollama`, which raise before any call.

## Definitions

A **turn** is one model request and its reply. A **tool call** is one
request by the model to run one tool.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

All are `kind: generated-test`: the HTTP loops run against a replaced
`urllib.request.urlopen`, the `claude-cli` loop against a fake `claude`
script.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- `D308`: initial spec.
