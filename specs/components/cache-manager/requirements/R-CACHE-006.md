# R-CACHE-006

**R-CACHE-006** — MUST expose a CLI inspection command reporting hit/miss
  and (on hit) the stored result's provenance-relevant fields for a given key
  or its components, without requiring direct access to the backing store's
  native tooling, exactly as `interface/cli.md` defines it, with a
  `stats` command reporting the local store's entry count.
