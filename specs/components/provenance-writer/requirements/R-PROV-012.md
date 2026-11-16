# R-PROV-012

**R-PROV-012** — `pipeline_version` MUST be this component's own
  version constant (`PIPELINE_VERSION`, mirroring `generator`'s
  `PROMPT_VERSION`/`GATE_VERSION` pattern) — bumped whenever this
  component's own manifest-population logic changes meaningfully, never
  computed from `ProvenanceInputs` or any other input (`D67`, found
  previously unsourced — `ProvenanceInputs` has no field it could come
  from).
