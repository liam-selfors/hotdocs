# R-PROV-017

**R-PROV-017** — `ProvenanceInputs` (`interface/data/ProvenanceInputs.md`)
  MUST be a real, importable `dataclass` in this component's own module,
  never only a type-hint name or a bare `Any` parameter.
  `write_provenance` still accepts an equivalent plain dict
  (`R-PROV-014`) (`D132`).
