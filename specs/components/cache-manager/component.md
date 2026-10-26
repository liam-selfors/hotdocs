---
id: comp-cache-manager
title: Cache Manager
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT]
uses_var: [VAR-CACHE-STORE-URL]
model_pin: claude-sonnet-5
sealed: false
---

# Cache Manager

## Purpose

A content-addressed cache: a get/put store keyed by
`(spec_bundle_hash, artifact/gate-inputs hash, gate_version, model_pin)`,
used by `generator`, `license-scanner`, and `secret-scanner` to avoid
redundant work on unchanged inputs.

## Rationale

Backs D13's "cache every gate" mandate and D11's cache-hit rollback
mechanism. Also the worked example behind D16: its one declared
behavioral guarantee (`interface/guarantees/G-CACHE-001.md`, a retrofit
of the consistency property `R-CACHE-003` already stated) is what let
`generator` narrow its own blast-radius dependency to specifically that
guarantee, via `depends_on_guarantees`.

## Scope

**In scope:** the key/value contract, key formation, fail-closed behavior on
store errors, protection against a caller writing a result under the wrong
gate's key.

**Out of scope:** deciding *what* is cacheable or *when* to check the cache
(that's each calling gate's own concern — `cache-manager` is a dumb,
trustworthy store, not a policy engine); the actual backing store's storage
engine/scaling characteristics (treated as an implementation detail behind
`VAR-CACHE-STORE-URL`).

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

Every criterion below is `kind: compiled` — a third real component, after
`spec-linter` and `impact-analyzer`, whose entire behavior is deterministic
store logic with no model call anywhere in it.

## Non-functional constraints

See `constraints.md`.

## Open questions

- ~~R-CACHE-003's "last-write-wins is safe only because gates are
  deterministic" assumption depends entirely on every other component in
  this system actually upholding its own determinism constraint. This
  component cannot verify that from the inside.~~ — resolved (`D37`):
  the precondition was stated too strongly, and has been corrected in
  `G-CACHE-001` rather than enforced from the outside. `license-scanner`/
  `secret-scanner` are byte-identical-deterministic by their own
  `constraints.md`, making last-write-wins trivially safe for them.
  `generator`/`test-author` are **not** — their own `constraints.md`
  already says so — but the guarantee never actually needed identical
  payloads, only that whichever write survives a race is itself an
  uncorrupted, legitimately-produced answer for that key, which their
  single-call-then-cache flow (`R-GEN-006`) already guarantees
  regardless of what a concurrent sibling call produces. See
  `AC-CACHE-009`.
- ~~Cache eviction/retention policy (how long entries live, whether
  there's a size bound on the backing store) is undecided~~ — resolved
  (`R-CACHE-008`): it has no correctness dimension to pin down. Eviction
  is always permitted, unconditionally — a caller already treats a miss
  as fully correct and expected regardless of cause (`R-CACHE-001`/
  `004`), so eviction only ever costs hit rate, never correctness. The
  exact policy stays an operational, backing-store-specific tuning
  choice, not a spec'd number.

## Change log

- Initial draft.
- `D37`: corrected `G-CACHE-001`'s determinism precondition and added
  `AC-CACHE-009` for the non-deterministic-writer case; resolves the
  open question above.
