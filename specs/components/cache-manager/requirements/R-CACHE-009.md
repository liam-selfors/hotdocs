# R-CACHE-009

**R-CACHE-009** — When `VAR-CACHE-STORE-URL` is absent, `get`/`put`
  MUST fall back to a local, file-based store under `.hotdocs/cache/`
  rather than treating every call as a miss. This is a different backing
  store, not a different contract: `R-CACHE-001`/`002`/`005`/`007`
  apply exactly the same way regardless of which backing is active, and
  `R-CACHE-004`'s fail-to-miss behavior on a backing-store error applies
  unconditionally to the local fallback too. `.hotdocs/cache/`'s data is
  governed entirely by this component's own schema (`CacheKey`/
  `CachedResult`) — it is colocated with `merge-tracker`'s `.hotdocs/`
  subdirectories for convenience only, not governed by that component's
  rules.

  This fallback is correctness-neutral regardless of project size: since
  `D30`, a `cache-manager` hit or miss only ever affects whether a model
  gets called again, never whether verification is skipped (that
  question moved to `provenance-checker`, which never consults this
  store) — so a local-only backing carries no risk beyond its own
  (single-machine) hit rate.

  The store URL is read from the environment variable
  `VAR_CACHE_STORE_URL`. No client for a shared store exists yet, so
  when it is set to any non-empty value, `get` MUST return `Miss` and
  `put` MUST validate the result (`R-CACHE-007`) and then store nothing:
  the unreachable-store case of `R-CACHE-004`, never a crash.
