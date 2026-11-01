---
id: comp-generator
title: Generator
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-cache-manager, comp-llm-endpoint]
depends_on_guarantees: [G-CACHE-001]
realizes: [P-ZERO-EDIT]
model_pin: claude-sonnet-5
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
`D3` retired the best-of-k loop; a fresh human merge attempt
(`R-MERGE-018`) is the only path back for a failed one.

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

Mixed `kind`: R-GEN-001–008, 010, 011 use an injected mock model
(`generated-test`, since exercising them means asserting on a mocked
call). R-GEN-009 is a pure path check, `compiled` like
`spec-bundle-assembler`. Whether 001–008 could become `compiled`
depends on `criterion-compiler` growing mock-injection support.

## Non-functional constraints

See `constraints.md`.

## Open questions

- ~~Retry/timeout policy for model errors~~ — resolved (R-GEN-011): no
  custom retry; a merge re-run (R-MERGE-017) is the retry.
- ~~Whether `.overrides.json` is read here or filtered upstream~~ —
  resolved: both. `generator` checks it directly (R-GEN-009) as the
  backstop; `R-GATE-007` is the primary skip-path.

## Change log

- Initial draft; first real hand-authored bootstrap implementation
  (`repo_root`/`llm_backend` params).
- `D35`: gained `_as_dict()`.
- `D37`: `R-GEN-013`, `dependency_usage` added. `PROMPT_VERSION` → `v2`.
- `D38`/`D39`: per-call nonce; cache only non-empty results.
  `PROMPT_VERSION` → `v3`, `GATE_VERSION` → `generator@1.1.0`.
- `D41`: `R-GEN-014`, `sys.modules` registration before `exec`.
  `PROMPT_VERSION` → `v4`.
- `D42`: fourth retry passed every testable `AC-GEN-*` criterion —
  first successful self-hosted regeneration; swapped in.
- `D46`: `R-GEN-015`, flat-module-or-package output required.
  `PROMPT_VERSION` → `v5`.
- `D64`: `R-GEN-016` — `hint` mode no longer writes `gen/`/cache.
- `D91`: retired this component's own CLI in favor of
  `component-gate-runner`'s `hotdocs generate`.
- `D138`/`D139`/`D159`: `R-GEN-018`/`019` — `repo_root`-relative
  dependency loading (a sealed one at its `source_path`) and
  dual-access on a dependency's top-level return. `v8`,
  `generator@1.5.0`.
- `D165`: strips a redundant `<component>/` path prefix
  (`R-GEN-015`); `GATE_VERSION` → `generator@1.6.0`.
