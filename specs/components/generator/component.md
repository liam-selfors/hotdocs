---
id: comp-generator
title: Generator
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-cache-manager]
realizes: [P-ZERO-EDIT]
uses_var: [VAR-ANTHROPIC-API-KEY, VAR-SECOND-MODEL-API-KEY]
model_pin: claude-sonnet-5
sealed: false
---

# Generator

## Purpose

Calls a pinned model to produce `gen/<component>/` from a `SpecBundle` —
cold, with no prior code (unless the bundle carries `hint_code`, D1),
exactly one candidate per invocation.

## Scope

**In scope:** constructing the model call from a `SpecBundle` and a model
identifier; checking/populating the cache before/after calling a model;
writing the result under `gen/<component>/`; recording what it did for
provenance.

**Out of scope, deliberately, and recorded here because the architecture
doc's dependency list only shows `spec-bundle-assembler` and
`cache-manager` — not `verifier-orchestrator`:** the best-of-k *retry loop*
across verification failures (D3). This component produces **exactly one
candidate per call** — single-shot, stateless about prior attempts.
Something above it (`merge-orchestrator`) calls this once per sample, checks
the result against `verifier-orchestrator`, and decides whether to call
again with a different seed. Putting the retry loop inside `generator`
would require it to depend on `verifier-orchestrator`, which nothing
upstream of this spec ever said it does — a gap this spec is resolving by
making the boundary explicit, not assuming an answer silently.

This single-shot design is also what lets `cross-model-divergence-checker`
reuse this exact component with a second model (R-GEN-004) instead of
duplicating generation logic — it only ever needs "one candidate from model
X," the same thing `merge-orchestrator` asks for.

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

Mixed `kind`, and deliberately so: R-GEN-001–008 describe behavior around an
external model call, tested with an injected mock model (same
dependency-injection pattern `spec-linter`'s `judge` parameter already
established) — `generated-test`, not `compiled`, since exercising them means
setting up and asserting on a mocked call, not purely structural text/graph
analysis. R-GEN-009 is a pure path-safety check with no model involved at
all, and is `compiled` like everything in `spec-bundle-assembler`.

Whether R-GEN-001–008 could instead be `compiled` depends on whether
`criterion-compiler`'s step grammar grows mock/dependency-injection support
— left as an open question there, not forced here.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Timeout/retry policy for transient model-API errors (distinct from
  R-GEN-008's "report a model-call error," which is about *classification*,
  not retry policy) — not addressed here; candidate home is `pipeline/`
  configuration once that exists for real, not this component's spec.
- Whether `gen/<component>/.overrides.json` paths should be read by this
  component directly, or whether `merge-orchestrator` should filter the
  write-set before calling `generator` at all. R-GEN-009 states the
  invariant; which component enforces it mechanically is not decided.

## Change log

- Initial draft.
