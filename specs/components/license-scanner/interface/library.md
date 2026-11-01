# Library

```
scan(component_id: str, repo_root: Path) -> LicenseScanResult
gate_version(repo_root: Path) -> str
```

`gate_version` returns exactly the `gate_version` string `scan` would
put on its result for the same `repo_root` and environment, without
scanning anything or touching `cache-manager` (`R-LICENSE-008`).

`scan` loads `cache-manager` from `<repo_root>/gen/cache-manager/` and
uses exactly four of its names: `CacheKey(spec_bundle_hash=...,
gate_inputs_hash=..., gate_version=..., model_pin=...)` to build the
key; `get(cache_key, repo_root=...)`; `CachedResult(gate_type="license_scanner",
payload=..., stored_at=...)`, whose `payload` is the `LicenseScanResult`'s
fields as a dict and whose `stored_at` this component computes
itself, as a UTC ISO-8601 string from its own clock; and, after a fresh scan, `put(cache_key,
cached_result, repo_root=...)`. Any stand-in for `cache-manager` must
provide all four, and no other `cache-manager` name is used — not
even a helper such as a timestamp function. A `get` result counts as a hit only if it has a
non-null `payload` (read with dual dict-or-attribute access); anything
else is a miss — never tested against `cache-manager`'s `Miss` type. `cache-manager` being unloadable means no cache
lookup, never a failed scan.
