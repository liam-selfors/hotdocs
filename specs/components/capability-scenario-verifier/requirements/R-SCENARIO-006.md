# R-SCENARIO-006

**R-SCENARIO-006** — The provenance key is `content_hash`:
  `"sha256:"` plus the SHA-256 over, in order, the bytes of the
  capability's own `specs/product/<name>.md`; then, for each component
  in the realizing set (`R-SCENARIO-002`) in component-id order, its id
  and every regular file under its code directory in sorted relative-path
  order — excluding any `__pycache__` directory and any file named
  `.provenance.json` — as relative path and bytes, every field
  `\0`-terminated. A component with no code directory contributes its id
  alone.

  It hashes actual code, deliberately not `spec_bundle_hash`: a
  spec-level hash would reopen the blind spot this component exists to
  close (`D2`). It also covers the capability's own file, so editing a
  scenario invalidates a prior pass.

  The record is `verification/capabilities/<capability_id>/.provenance.json`,
  a JSON object (sorted keys, two-space indent) with exactly
  `capability_id`, `gate_version`, `content_hash`, `realizing_components`
  (sorted ids), `capability_scenario_report` (this capability's report),
  `model` (string or `null`), and `seed`. Only `run_capability_gates`
  writes it, on a miss. `gate_version` is the module constant
  `GATE_VERSION`, `"capability_scenario_verifier@2.0.0"`; any change to
  `R-SCENARIO-005`'s execution or this hash MUST raise it here.
