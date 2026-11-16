---
id: comp-generator
title: Generator
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-cache-manager, comp-llm-endpoint]
depends_on_guarantees: [G-CACHE-001]
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
sealed: false
---

# Generator

## Purpose

Calls a pinned model to produce `gen/<component>/` from a `SpecBundle` —
cold, with no prior code (unless the bundle carries `hint_code`),
exactly one candidate per invocation.

## Rationale

`hint_code` is a feature-branch-only exception. Declares
`depends_on_guarantees: [G-CACHE-001]` (`D2`): R-GEN-005/006 trusts a
`get` hit as authoritative with no locking, safe only because
concurrent writers are last-write-wins-safe — not on `cache-manager`'s
other properties, so a change there won't pull in an unrelated blast
radius.

## Scope

**In scope:** constructing the model call from a `SpecBundle`, a model
identifier, and optional `retry_feedback` (`R-GEN-012`); checking the
cache first; in `cold` mode only, writing the result to
`gen/<component>/` and the cache (`R-GEN-016` — `hint` mode writes
neither); recording provenance.

**Out of scope (why `depends_on` excludes `verifier-orchestrator`):**
any retry of its own — exactly one candidate per call, single-shot.
`D3` retired the best-of-k loop; a human re-running
`hotdocs generate` is the only path back for a failed one.

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

All `generated-test`, with an injected mock model.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

- `D35`–`D268`: see the decisions. `D304`: truncated replies and a
  missing module are failures. `D305`: only `commit_cache` writes the
  cache.
