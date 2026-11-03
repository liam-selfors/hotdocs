# R-PROV-014

**R-PROV-014** — `build_manifest`/`write_provenance` MUST read every
  top-level field of `inputs` itself (`generation_result`,
  `verification_report`, `license_scan_result`, `secret_scan_result`,
  `provenance_hit`, `attempts`, `gate_versions`) using dual
  dict-or-attribute access, never a bare `.attr` access alone: this
  corpus's duck-typing convention (`D94`) means `ProvenanceInputs`
  itself, not only the values nested inside it, may arrive as either
  shape (`D128`). The same applies to `R-TRACK-012`'s dependency return
  values, one level removed.
