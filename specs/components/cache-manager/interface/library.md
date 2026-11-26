# Library

```
get(cache_key: CacheKey, *, repo_root: Path = None) -> CachedResult | Miss
put(cache_key: CacheKey, result: CachedResult, *, repo_root: Path = None) -> None
now_iso() -> str
stats(*, repo_root: Path = None) -> dict
class Miss
class SchemaValidationError(ValueError)
```

`CacheKey` and `CachedResult` are dataclasses with the fields of their
data documents, in that order, built by keyword. `Miss` is a class;
`get` reports a miss by returning an instance of it, never `None`, so a
caller tests `isinstance(result, Miss)`; any two `Miss` instances compare
equal. `put` raises `SchemaValidationError` for `R-CACHE-007`. `stats`
returns `{"entry_count": n}`, what the CLI's `stats` prints. `now_iso()` returns the current
UTC time as `YYYY-MM-DDTHH:MM:SSZ`, the form `CachedResult.stored_at`
takes.

Backed by the store at `VAR-CACHE-STORE-URL`. `get` never raises on a
backing-store error — it returns `Miss` (R-CACHE-004).

`repo_root` (`D30`) resolves which repository's `.hotdocs/cache/` the
local fallback (`R-CACHE-009`) reads/writes. Defaults to the current
working directory, matching `interface/cli.md`'s `--repo-root` flag.

Implements: `specs/architecture/cli-conventions.md`
