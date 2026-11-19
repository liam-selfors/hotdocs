---
id: comp-provenance-checker
title: Provenance Checker
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-bundle-assembler, comp-criterion-compiler, comp-test-author, comp-verifier-orchestrator, comp-license-scanner, comp-secret-scanner, comp-provenance-writer, comp-generator]
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

`cache-manager` records that a candidate was *produced*, never that
it was *verified* (`D29`). `.provenance.json` is written only from
`verifier-orchestrator`'s real output (`R-PROV-005`) and reaches a
committed directory only past `R-MERGE-011`, so a matching one on disk
*is* the proof.

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

Every criterion is `kind: generated-test` (`D43`).

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft (`D29`).
- `D47`: first real implementation (`verification/provenance-checker/
  BOOTSTRAP.md`).
- `D163`: gains `current_provenance_key`, the one definition of the
  `spec_bundle_hash`/`gate_versions` a hit compares, so the writer of
  `.provenance.json` and every checker of it agree. `R-PROVCHECK-006`
  covers the CLI (`D162`), whose hash validation rejected every real
  `sha256:`-prefixed hash.
- `D170`: `current_sealed_key`/`check_sealed_provenance` — the sealed
  counterpart (`R-PROVCHECK-007`/`008`); depends on `provenance-writer`
  for the manifest schema.
  Regenerated and landed at 13/13, `mutation_score` 0.91.
- `D313`: the key names the generator's version, so a generator or
  prompt change invalidates every manifest it produced.
- `D343`: the key includes each declared asset's definition, adapter
  and environment (`R-PROVCHECK-009`); a miss names its `reason`.
