# Library

```
get(cache_key: CacheKey, *, repo_root: Path = None) -> CachedResult | Miss
put(cache_key: CacheKey, result: CachedResult, *, repo_root: Path = None) -> None
```

Backed by the store at `VAR-CACHE-STORE-URL`. `get` never raises on a
backing-store error — it returns `Miss` (R-CACHE-004). `put` raises a
schema-validation error (not a silent no-op) if `result`'s shape doesn't
match what `cache_key.gate_version`'s gate type expects (R-CACHE-007).

`repo_root` (added `D48`, the same pre-existing-gap pattern
`llm-endpoint`'s `backend` parameter and `provenance-writer`'s
`ProvenanceInputs` each already were) — resolves which repository's
`.hotdocs/cache/` the local fallback (`R-CACHE-009`) reads/writes.
Defaults to the current working directory, matching `interface/cli.md`'s
own `--repo-root` flag, which implied this parameter existed all along.
