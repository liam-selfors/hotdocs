# R-PROV-004

**R-PROV-004** — `provenance_hit` MUST be populated from the caller's
  own `ProvenanceInputs` field of the same name — never recomputed or
  inferred from any gate's own result. Renamed from `cache_hit` by
  `D29`: this field has never meant "`cache-manager` had an entry" (a
  per-gate concern, e.g. `GenerationResult.cache_hit`) — it means
  `provenance-checker` reported a hit for the whole component, a fact
  only `merge-orchestrator` knows, since it's the one that asked.
