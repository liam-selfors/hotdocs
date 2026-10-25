---
id: comp-llm-endpoint
title: LLM Endpoint
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT, P-AMBIGUITY-GATE]
uses_var: [VAR-ANTHROPIC-API-KEY]
model_pin: claude-sonnet-5
sealed: false
---

# LLM Endpoint

## Purpose

A single, vendor-agnostic transport for every model call this pipeline
makes — `generator`, `test-author`, `spec-completeness-assistant`, and
the real `judge` callable `merge-orchestrator` wires into
`verifier-orchestrator`/`golden-scenario-verifier` all dispatch through
here instead of each independently knowing how to authenticate to, and
call, a specific vendor's API.

## Rationale

(D30.) Extracted once a real coupling was found, not invented
speculatively: `generator` and `test-author` each independently
declared `uses_var: [VAR-ANTHROPIC-API-KEY]`, and `merge-orchestrator`'s
`judge` wiring (`R-MERGE-004`) was "a direct call to the configured
model" with no component behind it at all. Swapping vendors meant
touching at least three places; `R-GEN-004` already treats the model
*identifier* as a vendor-agnostic string parameter, but nothing
previously owned the *mechanics* of actually calling whatever that
identifier names.

## Scope

**In scope:** resolving a model identifier to the right vendor backend;
authenticating and dispatching one completion request; normalizing every
backend's failure modes into one structured `model_call_error` vocabulary
(`R-GEN-008`'s definition, now owned here, given real queryable shape by
`D32`); writing a low-level, caller-agnostic call log of every dispatch
(`R-ENDPOINT-006`).

**Out of scope, deliberately:** prompt construction and response parsing
for any specific task (what a *generation* prompt or a *judge* prompt
looks like stays with each caller, the same way `prompt_version` is
already tracked per-caller, not globally) — this component only knows
"send this text to this model, return what came back." Also out of
scope: retry-with-backoff (`R-ENDPOINT-004`, same posture `D21` already
established for `generator`, now stated at the layer that actually
touches the network).

**v1 scope, named explicitly:** exactly one backend (Anthropic). Not
because multi-vendor support isn't the point — it's the whole point of
this component existing — but because this project's own
anti-premature-abstraction stance (`D18`, `D20`) says build the seam, not
every implementation behind it, until a second vendor is actually needed.
A second backend is an additive implementation behind the same
resolve/dispatch split (`R-ENDPOINT-002`/`003`), not a rework.

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

None — v1's single-backend scope is a deliberate decision (above), not an
open question.

## Change log

- Initial draft (D30).
