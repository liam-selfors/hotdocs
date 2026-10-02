---
id: comp-generator
title: Generator
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-cache-manager]
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

- **R-GEN-001** — Given a `SpecBundle` in `cold` mode, the model call MUST
  be constructed from exactly the bundle's `spec` / `interface` /
  `constraints` / `dependency_interfaces` / `vars` / `glossary` fields —
  never `hint_code` (which is `null` in cold mode anyway, per
  `spec-bundle-assembler` R-ASSEMBLE-008) and never the component's current
  `gen/<component>/` content from any other source.
- **R-GEN-002** — Given a `SpecBundle` in `hint` mode, the model call MUST
  additionally include `hint_code` as context, clearly distinguished from
  the cold bundle fields in the prompt — never silently merged in a way
  that makes a later audit unable to tell which parts of the prompt were
  "the spec" versus "the existing code."
- **R-GEN-003** — The prompt template MUST be frozen and versioned; the
  exact template text and its version MUST be recorded in the output
  (`prompt_version`, feeding D7's provenance manifest).
- **R-GEN-004** — The model identifier MUST be an explicit parameter, never
  hardcoded to "the canonical pin" — this is the single mechanism that lets
  `cross-model-divergence-checker` call this same component with a second
  model rather than reimplementing generation.
- **R-GEN-005** — Before calling any model, generation MUST check
  `cache-manager` using the key `(spec_bundle_hash, gate_inputs_hash,
  gate_version, model_pin)`; on a cache hit, the cached result MUST be
  returned and no model call MUST occur.
- **R-GEN-006** — On a cache miss, after a successful model call, the result
  MUST be written to `cache-manager` under the same key before being
  returned.
- **R-GEN-007** — The seed/sample index used for this call MUST be recorded
  in the output (feeding D3's `sample_index` provenance field).
- **R-GEN-008** — A model-call error (network, auth, rate-limit, timeout)
  MUST be reported as a distinct failure mode from "the model responded but
  the generated code may be wrong" — the former is what D10's
  fallback/halt logic reacts to; the latter is what `merge-orchestrator`'s
  best-of-k retry reacts to. Conflating them would misroute which recovery
  mechanism engages.
- **R-GEN-009** — Writing output MUST be confined to `gen/<component>/` for
  the target component only. It MUST NOT write to any `sealed` component's
  `source_path`, and MUST NOT overwrite a file listed in that component's
  `gen/<component>/.overrides.json` (the two declared cold-regen exemptions,
  §9) — generation must never silently clobber a declared hands-off path.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`GenerationResult` schema).

## Acceptance criteria

See `acceptance.md`.

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
