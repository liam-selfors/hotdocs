---
id: comp-cache-manager
title: Cache Manager
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-ZERO-EDIT]
uses_var: [VAR-CACHE-STORE-URL]
model_pin: claude-opus-5-5
sealed: false
---

# Cache Manager

## Purpose

A content-addressed cache: a get/put store keyed by
`(spec_bundle_hash, artifact/gate-inputs hash, gate_version, model_pin)`,
used by `generator`, `test-author`, `license-scanner`, and
`secret-scanner` to avoid redundant work on unchanged inputs.

## Rationale

See `D30`, `D2`.

## Scope

**In scope:** the key/value contract, key formation, fail-closed behavior on
store errors, protection against a caller writing a result under the wrong
gate's key.

**Out of scope:** deciding *what* is cacheable or *when* to check the cache
(that's each calling gate's own concern — `cache-manager` is a dumb,
trustworthy store, not a policy engine); the actual backing store's storage
engine/scaling characteristics (treated as an implementation detail behind
`VAR-CACHE-STORE-URL`, including whether it resolves to a shared store or
the local fallback, `R-CACHE-009`); deciding whether a component's work was
ever *verified*, not just *produced* — `provenance-checker`'s job
(`D30`), using a different data source entirely.

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

`D24`, `D30`, `D40`, `D212`.
