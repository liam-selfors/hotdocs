---
id: comp-cache-manager-interface
title: Cache Manager — Interface
status: draft
owners: [pipeline-team]
---

# Cache Manager — Interface

## Library

```
get(cache_key: CacheKey) -> CachedResult | Miss
put(cache_key: CacheKey, result: CachedResult) -> None
```

Backed by the store at `VAR-CACHE-STORE-URL`. `get` never raises on a
backing-store error — it returns `Miss` (R-CACHE-004). `put` raises a
schema-validation error (not a silent no-op) if `result`'s shape doesn't
match what `cache_key.gate_version`'s gate type expects (R-CACHE-007).

## CLI

```
hotdocs cache inspect --spec-bundle-hash=<h> --gate-inputs-hash=<h> \
  --gate-version=<v> --model-pin=<p> [--repo-root=<dir>]
hotdocs cache stats [--repo-root=<dir>]
```

- `inspect` — reports hit/miss for the given key; on hit, prints the stored
  result's provenance-relevant fields (not the full payload).
- `stats` — aggregate hit/miss counts, feeding the corpus-wide "cache hit
  rate" metric (`notes/metrics.md`, Generation phase).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Command completed (a reported "miss" is still exit `0` — it's an answer, not a failure). |
| `2` | Usage error (malformed key component, unreachable store counted as a `Miss`/empty stats, not an exit-2 error — per R-CACHE-004). |

## Data: `CacheKey`

```json
{
  "spec_bundle_hash": "sha256:...",
  "gate_inputs_hash": "sha256:...",
  "gate_version": "license_scanner@3.1.0",
  "model_pin": "claude-sonnet-5"
}
```

## Data: `CachedResult`

```json
{
  "gate_type": "license_scanner",
  "payload": { "...": "gate-specific result shape" },
  "stored_at": "2026-10-02T00:00:00Z"
}
```

`gate_type` MUST match one of the known gate types (`compiler`,
`generated_test`, `llm_judge`, `cross_model_check`, `license_scanner`,
`secret_scanner`) and `payload`'s shape MUST match that type's expected
schema — enforced by `put` (R-CACHE-007), not left to the caller's
discipline.
