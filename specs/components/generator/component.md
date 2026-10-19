---
id: comp-generator
title: Generator
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-cache-manager]
depends_on_guarantees: [G-CACHE-001]
realizes: [P-ZERO-EDIT]
uses_var: [VAR-ANTHROPIC-API-KEY]
model_pin: claude-sonnet-5
sealed: false
---

# Generator

## Purpose

Calls a pinned model to produce `gen/<component>/` from a `SpecBundle` —
cold, with no prior code (unless the bundle carries `hint_code`, D1),
exactly one candidate per invocation.

Declares `depends_on_guarantees: [G-CACHE-001]` — the D16 worked example.
R-GEN-005/006's whole cache-check-before-call / cache-write-after-call
behavior genuinely depends on `cache-manager`'s consistency guarantee: a
`get` that returns a hit is trusted as authoritative with no locking of its
own, which is only safe because concurrent writers for the same key are
safe under last-write-wins (G-CACHE-001). It does *not* depend on
`cache-manager`'s other properties (store-error fail-closed behavior, CLI
inspection, etc.) in any way this component's own logic cares about — so a
future change to *those* should not, and now will not, pull this component
into an unrelated blast radius.

## Scope

**In scope:** constructing the model call from a `SpecBundle`, a model
identifier, and (optionally) `retry_feedback` (R-GEN-010); checking/
populating the cache before/after calling a model; writing the result
under `gen/<component>/`; recording what it did for provenance.

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

`retry_feedback` (R-GEN-010) does not change any of this: this component
still produces exactly one candidate per call and still has no memory of
its own across calls — `merge-orchestrator` is still the one deciding
whether, and with what feedback, to call again. The only thing that
changed is that one of the inputs a caller MAY supply is now a derived
fact about a *previous* call in the same sequence, not just a fresh seed.

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

Mixed `kind`, and deliberately so: R-GEN-001–008 and R-GEN-010 describe
behavior around an external model call, tested with an injected mock model
(same dependency-injection pattern `spec-linter`'s `judge` parameter already
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
