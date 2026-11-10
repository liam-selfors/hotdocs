---
id: comp-llm-endpoint
title: LLM Endpoint
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
uses_var: [VAR-ANTHROPIC-API-KEY, VAR-OPENAI-API-KEY, VAR-GEMINI-API-KEY, VAR-HOTDOCS-CONFIG]
model_pin: claude-sonnet-5
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

(D18.) Extracted once a real coupling was found, not invented
speculatively: `generator` and `test-author` each independently
declared `uses_var: [VAR-ANTHROPIC-API-KEY, VAR-OPENAI-API-KEY, VAR-GEMINI-API-KEY, VAR-HOTDOCS-CONFIG]`, and `merge-orchestrator`'s
`judge` wiring (now `R-MERGE-014`, `D76`) was "a direct call to the
configured model" with no component behind it at all. Swapping vendors meant
touching at least three places; `R-GEN-004` already treats the model
*identifier* as a vendor-agnostic string parameter, but nothing
previously owned the *mechanics* of actually calling whatever that
identifier names.

## Scope

**In scope:** resolving a model identifier to a provider; reading the
optional configuration; authenticating and dispatching one completion
request; normalizing every
backend's failure modes into one structured `model_call_error` vocabulary
(`R-GEN-008`'s definition, now owned here, given real queryable shape by
`D20`); writing a low-level, caller-agnostic call log of every dispatch
(`R-ENDPOINT-006`).

**Out of scope, deliberately:** prompt construction and response parsing
for any specific task (what a *generation* prompt or a *judge* prompt
looks like stays with each caller, the same way `prompt_version` is
already tracked per-caller, not globally) — this component only knows
"send this text to this model, return what came back." Also out of
scope: retry-with-backoff (`R-ENDPOINT-004`, same posture `D7` already
established for `generator`, now stated at the layer that actually
touches the network).

**Providers, named explicitly:** `claude-cli`, `anthropic`, `openai`,
`openai-compatible`, `gemini`, and `ollama` (`R-ENDPOINT-003`), chosen by
the model string and an optional committed `hotdocs.toml` that never holds
a secret (`R-ENDPOINT-007`). Further providers are additive adapters
behind the same resolve/dispatch split. The setup helpers `hotdocs init`
uses live here too (`R-ENDPOINT-009`), so the provider list has one owner.

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

Mixed `kind`, mirroring `generator`'s own split: the external call itself
is `generated-test` (exercised via an injected mock backend); backend
resolution and credential-safety are pure, deterministic checks,
`compiled`.

## Non-functional constraints

See `constraints.md`.

## Open questions

- `ollama` silently truncates a prompt longer than its server's context
  window unless `num_ctx` is passed; no default is set, since a safe
  value depends on the model and the machine (`D182`).

## Change log

Each decision holds its full rationale.

- `D18`, `D33`: first, hand-written implementation through the `claude`
  command. `D34`/`D35`/`D52`: timeout floor, `--tools ""`. `D82`:
  `--safe-mode` without an API key.
- `D180`–`D183`: the six providers, `hotdocs.toml`, setup helpers.
- `D209`, `D220`, `D221`, `D223`, `D224`: the interface stated exactly for
  generation from this spec. `D225`: the `claude` command's whole reply.
