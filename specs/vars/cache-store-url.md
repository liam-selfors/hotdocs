---
id: VAR-CACHE-STORE-URL
title: Cache Store URL
status: draft
owners: [pipeline-team]
---

# VAR-CACHE-STORE-URL

- **required:** yes
- **type:** url
- **sensitivity:** non-secret
- **description:** Location of the content-addressed gate cache (D13) that
  `cache-manager` reads and writes — keyed by `(spec_bundle_hash,
  artifact/gate-inputs hash, gate_version, model_pin)`.
- **example:** `redis://cache.internal:6379/0`
