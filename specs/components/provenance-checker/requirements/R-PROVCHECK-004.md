# R-PROVCHECK-004

**R-PROVCHECK-004** — MUST be read-only: MUST NOT write, modify, or
  delete `.provenance.json` or any other file. Mirrors `cache-manager`'s
  own `get`-side discipline (`R-CACHE-001`), applied here to committed
  repository content instead of a cache store.
