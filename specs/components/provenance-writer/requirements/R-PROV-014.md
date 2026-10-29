# R-PROV-014

**R-PROV-014** — `build_manifest`/`write_provenance` MUST read every
  top-level field of `inputs` itself (`generation_result`,
  `verification_report`, `license_scan_result`, `secret_scan_result`,
  `provenance_hit`, `attempts`, `gate_versions`) using dual
  dict-or-attribute access, never a bare `.attr` access alone — this
  corpus's duck-typing convention (`D94`) means `ProvenanceInputs`
  itself, not only the values nested inside it, may arrive as either
  shape, since `interface/data/ProvenanceInputs.md`'s own example
  renders it as a plain JSON object.

  Found via a first real cold-generation attempt (`D128`): the
  candidate's own `_field()` helper already applied dual access
  correctly to fields *nested inside* `generation_result` and the
  rest, but `build_manifest`'s own top-level reads
  (`inputs.generation_result`, `inputs.license_scan_result`, ...)
  were bare attribute access throughout — a dict-shaped `inputs`
  crashed outright with `AttributeError` before `_field()` ever ran.
  The identical bug class `R-TRACK-012` already closed for
  `provenance-tracker`'s own dependency-result reads, one level up
  the call: there, the return value of a *called* dependency; here,
  a parameter the caller hands in directly — the same duck-typing
  convention applies either way.
