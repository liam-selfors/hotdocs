---
id: comp-provenance-checker
title: Provenance Checker
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-criterion-compiler, comp-test-author, comp-verifier-orchestrator, comp-license-scanner, comp-secret-scanner, comp-provenance-writer, comp-generator, comp-run-environment]
realizes: [P-ZERO-EDIT]
uses_var: [VAR-TRUST-JUDGE-PROVENANCE]
model_pin: claude-opus-5-5
sealed: false
---

# Provenance Checker

## Purpose

Decides whether a component's already-committed `.provenance.json`
proves it was already verified against the exact spec state a merge is
currently checking — so `component-gate-runner` can safely skip
regeneration and re-verification for that component.

## Rationale

See `D29`: a matching manifest on disk is the proof of verification.

## Scope

**In scope:** reading a component's committed `gen/<component>/
.provenance.json`, comparing its `spec_bundle_hash` and `gate_versions`
against the caller-supplied current ones (defined once, by
`current_provenance_key`), and — when they match —
deciding whether to honor that match given
`VAR-TRUST-JUDGE-PROVENANCE` and whether the embedded
`verification_report` includes any `llm-judge`-kind criterion.

Also, for a sealed component (`D170`): computing its current key — owners,
a hash of its source, the verifier version — and deciding whether its
sealed provenance manifest (`provenance-writer`'s schema) is valid and
current.

**Out of scope:** computing the current `spec_bundle_hash`
(`spec-bundle-assembler`'s job); writing or modifying `.provenance.json`
(`provenance-writer`'s job); deciding whether a *candidate* should be
regenerated to avoid a redundant model call (`cache-manager`'s job).

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


## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

`D29`, `D47`, `D162`, `D163`, `D170`, `D313`, `D343`, `D344`, `D345`,
`D379`.
