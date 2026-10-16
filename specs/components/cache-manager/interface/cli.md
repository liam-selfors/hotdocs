# CLI

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
