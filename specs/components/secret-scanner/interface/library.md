# Library

```
scan(repo_root: Path) -> SecretScanResult
scan_files(paths: list[Path]) -> SecretScanResult
gate_version(repo_root: Path) -> str
```

`scan` is the full, cache-aware form. `scan_files` is the precommit form —
no cache lookup, no `gate_version` dependency, since it's meant to run
before a commit exists to key anything on. `gate_version` returns
exactly the `gate_version` string `scan` would put on its result, without
scanning anything or touching `cache-manager` (`R-SECRET-010`).

`scan` loads `cache-manager` from `<repo_root>/gen/cache-manager/` and
uses exactly four of its names: `CacheKey(spec_bundle_hash=...,
gate_inputs_hash=..., gate_version=..., model_pin=...)` to build the
key; `get(cache_key, repo_root=...)`; `CachedResult(gate_type="secret_scanner",
payload=..., stored_at=...)`, whose `payload` is the `SecretScanResult`'s
fields as a dict and whose `stored_at` this component computes
itself, as a UTC ISO-8601 string from its own clock; and, after a fresh scan, `put(cache_key,
cached_result, repo_root=...)`. Any stand-in for `cache-manager` must
provide all four, and no other `cache-manager` name is used — not
even a helper such as a timestamp function. A `get` result counts as a hit only if it has a
non-null `payload` (read with dual dict-or-attribute access); anything
else is a miss — never tested against `cache-manager`'s `Miss` type. `cache-manager` being unloadable means no cache
lookup, never a failed scan.

`scan` covers every file under `specs/`, `gen/`, and `verification/`,
including any stand-in dependency a test places there, so a stand-in
must embed no high-entropy string such as a temporary-directory path;
it reads any such value from an environment variable instead. The
compliance webhook is POSTed with `urllib.request.urlopen` and nothing
else, so a test replaces that function rather than starting an HTTP
server.
