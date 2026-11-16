# `component_provenance` (view)

```
component_id        TEXT
spec_bundle_hash     TEXT
...                  --  every other .provenance.json field (SPEC_GUIDELINES.md §7), passed through as-is
verification_report  STRUCT
license_scan         STRUCT
secret_scan          STRUCT
provenance_hit       BOOLEAN
```

One row per component (`R-GQE-005`), read directly from
`provenance-writer`'s already-written `.provenance.json` manifests —
never recomputed, never a live call into `verifier-orchestrator`/
`license-scanner`/`secret-scanner`.
