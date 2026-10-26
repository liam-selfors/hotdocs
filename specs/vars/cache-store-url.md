---
id: VAR-CACHE-STORE-URL
title: Cache Store URL
status: draft
owners: [pipeline-team]
---

# VAR-CACHE-STORE-URL

- **required:** no
- **type:** url
- **sensitivity:** non-secret
- **description:** Location of the content-addressed gate cache (D13) that
  `cache-manager` reads and writes — keyed by `(spec_bundle_hash,
  artifact/gate-inputs hash, gate_version, model_pin)`. Absent means
  `cache-manager` falls back to a local, file-based store under
  `.hotdocs/cache/` (`R-CACHE-009`, `D39`) rather than having no cache
  at all — the right default for a single-developer project with no
  shared infrastructure to point at, but not a substitute for a real
  shared store on a project where merges run across multiple machines
  or CI runners, which gain nothing from a store scoped to just one of
  them.
- **example:** `redis://cache.internal:6379/0`
