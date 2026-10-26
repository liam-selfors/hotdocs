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
`depends_on_guarantees: [G-CACHE-001]` — the D16 worked example:
R-GEN-005/006's whole cache-check-before-call / cache-write-after-call
behavior genuinely depends on `cache-manager`'s consistency guarantee: a
`get` that returns a hit is trusted as authoritative with no locking of
its own, which is only safe because concurrent writers for the same key
are safe under last-write-wins (G-CACHE-001). It does *not* depend on
`cache-manager`'s other properties (store-error fail-closed behavior,
CLI inspection, etc.) in any way this component's own logic cares about
— so a future change to *those* should not, and now will not, pull this
component into an unrelated blast radius.

## Scope

**In scope:** constructing the model call from a `SpecBundle`, a model
identifier, and optionally `retry_feedback` (`R-GEN-012`, restored by
`D33` after `D31` mistakenly dropped it); checking/populating the cache
before/after calling a model; writing the result under
`gen/<component>/`; recording what it did for provenance.

**Out of scope, deliberately, and recorded here because the architecture
doc's dependency list only shows `spec-bundle-assembler` and
`cache-manager` — not `verifier-orchestrator`:** any retry of its own.
This component produces **exactly one candidate per call, ever** —
single-shot, stateless about prior attempts, with no notion of a retry
sequence at all. `merge-orchestrator` calls this once per component per
merge attempt (`R-MERGE-005`); since `D31` retired the best-of-k retry
loop that used to call it again with different feedback on a
verification failure, this component is never called a second time
within one merge regardless of outcome — a fresh merge attempt (a human
re-running `hotdocs merge`, `R-MERGE-018`) is the only path back to
`generator` for a component whose one attempt failed. Putting any retry
logic inside `generator` would still require it to depend on
`verifier-orchestrator`, which nothing upstream of this spec says it
does — the boundary stays explicit for the same reason it always was,
even though there's no longer a loop on the other side of it to serve.

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

Whether R-GEN-001–008 could instead be `compiled` depends on whether
`criterion-compiler`'s step grammar grows mock/dependency-injection support
— left as an open question there, not forced here.

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

- Initial draft.
- `D50`: first real `gen/generator/` implementation — a hand-authored
  bootstrap exception, structurally permanent like `llm-endpoint`:
  nothing could cold-regenerate the component that does the
  cold-regenerating. `generate()` gained `repo_root`/`llm_backend`
  parameters (`interface/library.md`), two real, pre-existing gaps.
  `cache-manager`'s `gate_type` registry gained `generator` as a sixth
  known type — also a real, pre-existing gap.
