# Library

```
get(cache_key: CacheKey) -> CachedResult | Miss
put(cache_key: CacheKey, result: CachedResult) -> None
```

Backed by the store at `VAR-CACHE-STORE-URL`. `get` never raises on a
backing-store error — it returns `Miss` (R-CACHE-004). `put` raises a
schema-validation error (not a silent no-op) if `result`'s shape doesn't
match what `cache_key.gate_version`'s gate type expects (R-CACHE-007).
