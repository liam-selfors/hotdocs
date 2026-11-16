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

This is the mechanism behind the original claim that a merge whose spec
state exactly matches an already-verified prior state can skip
regeneration and re-verification entirely. That claim was previously
implemented (`D29`) by asking `cache-manager` a question its own data
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

Every criterion is `kind: generated-test` (`D43`) — reading a committed
file, comparing a hash, and reading one boolean var is pure,
deterministic logic that needs no model or judgment, but none of this
component's criteria are actually written in `specs/architecture/
step-phrase-grammar.md`'s fixed step vocabulary, so `kind: compiled`
would not describe how they're really verified.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft (`D29`).
- `D47`: first real implementation, via three real `generate()`
  retries (the first two found real, corpus-wide gaps — `D45`'s
  `component_id`-to-slug mapping, `D46`'s output-layout requirement —
  fixed in `generator`/`glossary.md`, not here). `gen/provenance-
  checker/` is now a real top-level package. See `verification/
  provenance-checker/BOOTSTRAP.md` for the full account.
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
