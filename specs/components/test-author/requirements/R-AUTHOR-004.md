# R-AUTHOR-004

**R-AUTHOR-004** — Before calling any model, MUST check `cache-manager`
  using a key derived from `(criterion content hash, gate_inputs_hash,
  gate_version, model)` — mirrors `generator`'s R-GEN-005 exactly, at
  criterion granularity instead of component granularity.
