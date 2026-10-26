---
id: comp-provenance-checker
title: Provenance Checker
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT]
uses_var: [VAR-TRUST-JUDGE-PROVENANCE]
sealed: false
---

# Provenance Checker

## Purpose

Decides whether a component's already-committed `.provenance.json`
proves it was already verified against the exact spec state a merge is
currently checking — so `merge-orchestrator` can safely skip
regeneration and re-verification for that component.

## Rationale

This is the mechanism behind the claim (`D11`) that a merge whose spec
state exactly matches an already-verified prior state can skip
regeneration and re-verification entirely. That claim was previously
implemented (`D39`) by asking `cache-manager` a question its own data
could never answer: `cache-manager` records that a candidate was
*produced*, not that it was ever *verified* — `verifier-orchestrator`
never writes to it. A candidate that failed verification gets cached
under the same key as one that passed, with nothing distinguishing them
on a later `get`. `.provenance.json` doesn't have this problem: it is
written only by `provenance-writer`, only from `verifier-orchestrator`'s
real output (`R-PROV-005`), and only ever reaches a component's
committed directory because `R-MERGE-011` already blocked the commit
otherwise — the same discipline that makes `SPEC_GUIDELINES.md` §7 call
it an SBOM/SLSA-style attestation. The fact a matching one exists on
disk, for the exact current `spec_bundle_hash`, *is* the proof — no
separate store, no new cryptography, nothing `cache-manager` needs to
change.

## Scope

**In scope:** reading a component's committed `gen/<component>/
.provenance.json`, comparing its `spec_bundle_hash` and `gate_versions`
against the caller-supplied current ones, and — when they match —
deciding whether to honor that match given
`VAR-TRUST-JUDGE-PROVENANCE` and whether the embedded
`verification_report` includes any `llm-judge`-kind criterion.

**Out of scope:** computing the current `spec_bundle_hash`
(`spec-bundle-assembler`'s job); writing or modifying `.provenance.json`
(`provenance-writer`'s job); deciding whether a *candidate* should be
regenerated to avoid a redundant model call — that's `cache-manager`'s
narrower, still-unchanged job, answering a different question
("has this exact work already been done") from the one this component
answers ("has this exact work already been proven correct").

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

Every criterion is `kind: compiled` — reading a committed file, comparing
a hash, and reading one boolean var is pure, deterministic logic;
nothing here needs a model or judgment.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft (`D39`).
