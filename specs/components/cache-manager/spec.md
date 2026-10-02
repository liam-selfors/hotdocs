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

The content-addressed cache backing D13's "cache every gate" mandate and
D11's cache-hit rollback mechanism: a get/put store keyed by
`(spec_bundle_hash, artifact/gate-inputs hash, gate_version, model_pin)`,
used by `generator`, `cross-model-divergence-checker`, `license-scanner`, and
`secret-scanner`.

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

- **R-CACHE-001** — `get` MUST return either the stored result for an exact
  key match, or a definitive miss — never a partial, approximate, or
  "probably equivalent" result.
- **R-CACHE-002** — The cache key MUST be exactly the 4-tuple
  `(spec_bundle_hash, artifact/gate-inputs hash, gate_version, model_pin)`
  (D13), computed identically regardless of which calling component invokes
  `get`/`put` — the key-formation logic is this component's responsibility,
  not each caller's, so every gate hashes consistently.
- **R-CACHE-003** — `put` MUST be safe to call concurrently (from parallel
  gate runs, per D13's "parallelize independent gates") without corrupting
  either entry. Conflict policy: last-write-wins per key is acceptable *only*
  if the two writers would have produced the same result for the same key by
  construction (D13's determinism requirement on every gate) — `put` MUST NOT
  silently merge or partially overwrite a stored result.
- **R-CACHE-004** — On any backing-store error (unreachable
  `VAR-CACHE-STORE-URL`, timeout, corrupt stored entry), `get` MUST return a
  miss, never raise an exception or crash the caller — the same "the tool
  must keep working" posture D10 established for model availability, applied
  here to the cache: a broken cache degrades to "nothing is cached yet," not
  to a pipeline outage.
- **R-CACHE-005** — `gate_version` MUST be part of the lookup key itself, not
  metadata checked after retrieval — a `get` for `gate_version: "2.0.0"` MUST
  NOT return an entry stored under `gate_version: "1.0.0"`, even if every
  other key component matches.
- **R-CACHE-006** — MUST expose a CLI inspection command reporting hit/miss
  and (on hit) the stored result's provenance-relevant fields for a given key
  or its components, without requiring direct access to the backing store's
  native tooling.
- **R-CACHE-007** — `put` MUST reject (not silently accept) a result payload
  whose shape doesn't match the schema expected for the `gate_version`'s
  declared gate type — guards against cache poisoning from a caller bug
  writing, e.g., a `LintReport`-shaped payload under a `license_scanner`
  `gate_version`.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`CacheKey` / `CachedResult` schemas).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

- R-CACHE-003's "last-write-wins is safe only because gates are
  deterministic" assumption depends entirely on every other component in
  this system actually upholding its own determinism constraint. This
  component cannot verify that from the inside — it's a cross-cutting
  assumption this spec inherits rather than enforces. Not resolved here;
  flagged as a standing dependency on every gate's own constraints.md.
- Cache eviction/retention policy (how long entries live, whether there's a
  size bound on the backing store) is undecided — out of scope for this
  draft, deferred to an operational concern rather than a correctness one.

## Change log

- Initial draft.
