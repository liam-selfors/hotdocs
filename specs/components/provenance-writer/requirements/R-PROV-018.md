# R-PROV-018

**R-PROV-018** — `write_sealed_provenance(component_id, inputs,
  repo_root)` MUST write exactly one file,
  `<repo_root>/<source_path>/.sealed-provenance.json`, whose content is
  a valid sealed provenance manifest
  (`interface/data/SealedProvenance.md`): the six input fields copied
  unchanged, `characterization` derived from `verification_report` as
  that document states, `kind` and `version` fixed, and `written_at`
  this component's own write time (`R-PROV-008`). Keys are written in
  the document's order, two-space indented, with a trailing newline. It
  creates `<source_path>` if absent and writes nothing else: no
  `gen/` or `verification/` copy, no change to any other file.
