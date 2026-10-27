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

`hint_code` is a feature-branch-only exception (D1). Declares
`depends_on_guarantees: [G-CACHE-001]` (D16 worked example):
R-GEN-005/006's cache-check/cache-write behavior trusts a `get` hit as
authoritative with no locking of its own, safe only because concurrent
writers are last-write-wins-safe (G-CACHE-001) — it does not depend on
`cache-manager`'s other properties, so a change to those won't pull
this component into an unrelated blast radius.

## Scope

**In scope:** constructing the model call from a `SpecBundle`, a model
identifier, and optionally `retry_feedback` (`R-GEN-012`, restored by
`D33` after `D31` mistakenly dropped it); checking the cache before
calling a model; in `cold` mode only, writing the result to
`gen/<component>/` and to the cache (`R-GEN-016` — a `hint`-mode call
reads the cache but never writes to either destination); recording
what it did for provenance.

**Out of scope, deliberately (explains why `depends_on` excludes
`verifier-orchestrator`):** any retry of its own. Exactly one candidate
per call, ever — single-shot, stateless about prior attempts. `D31`
retired the best-of-k retry loop; `merge-orchestrator` calls this once
per component per merge attempt (`R-MERGE-005`), and a fresh human
merge attempt (`R-MERGE-018`) is the only path back for a failed one.
Retry logic here would require depending on `verifier-orchestrator`,
which nothing upstream says it does.

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

Mixed `kind`, and deliberately so: R-GEN-001–008, R-GEN-010, and R-GEN-011
describe behavior around an external model call, tested with an injected
mock model (same dependency-injection pattern `spec-linter`'s `judge`
parameter already established) — `generated-test`, not `compiled`, since
exercising them means setting up and asserting on a mocked call, not purely
structural text/graph analysis. R-GEN-009 is a pure path-safety check with
no model involved at all, and is `compiled` like everything in
`spec-bundle-assembler`.

Whether R-GEN-001–008 could instead be `compiled` depends on
`criterion-compiler`'s step grammar growing mock-injection support —
an open question there, not forced here.

## Non-functional constraints

See `constraints.md`.

## Open questions

- ~~Timeout/retry policy for transient model-API errors (distinct from
  R-GEN-008's "report a model-call error," which is about *classification*,
  not retry policy)~~ — resolved (R-GEN-011): no custom retry/backoff logic
  here, trust `llm-endpoint`'s own bounded-call guarantee (D30), report
  `model_call_error` once, and let a merge re-run (R-MERGE-017) be the
  retry mechanism, which is already free given
  R-GEN-006's cache-on-success-only behavior.
- ~~Whether `.overrides.json` paths should be read by this component
  directly, or whether `merge-orchestrator` should filter the write-set
  first~~ — resolved: both, as two independent layers. `generator` reads
  sealed/`.overrides.json` status directly as a precondition check, before
  any model call (R-GEN-009, refined). `merge-orchestrator` gained its own
  routing requirement (R-MERGE-015) to skip calling `generator` for a
  sealed component in the first place — the primary, cost-aware path;
  `generator`'s own check is the independent backstop, not the only
  enforcement.

## Change log

Full narrative for each entry lives in its own `specs/decisions/D<N>.md`
— this log is a terse pointer index, not a restatement.

- Initial draft.
- `D50`: first real `gen/generator/` implementation (hand-authored
  bootstrap exception); `repo_root`/`llm_backend` params added.
- `D51`/`D53`: used to regenerate `llm-endpoint`; gained `_as_dict()`.
- `D54`: a self-regeneration attempt failed to import, not swapped in.
- `D55`: `R-GEN-013`, `dependency_usage` added to the prompt
  (`D54`'s fix). `PROMPT_VERSION` → `v2`.
- `D56`: per-call nonce (delimiter collision fix); cache only
  non-empty results. `PROMPT_VERSION` → `v3`, `GATE_VERSION` →
  `generator@1.1.0`.
- `D57`: `R-GEN-014`, `sys.modules` registration before `exec`.
  `PROMPT_VERSION` → `v4`.
- `D58`: fourth retry passed all testable `AC-GEN-*` criteria — first
  successful self-hosted regeneration; swapped in.
- `D62`: `R-GEN-015`, flat-module-or-package output required.
  `PROMPT_VERSION` → `v5`.
- `D81`: `R-GEN-016` — `hint`-mode calls wrote to `gen/` and the cache
  like `cold` mode; since `spec_bundle_hash` excludes `hint_code`,
  that could poison a later `cold` build's cache slot. Fixed: reads
  the cache, writes to neither destination.
