# R-PROV-019

**R-PROV-019** — `write_sealed_provenance` MUST validate before
  writing, never invent. If `component_id` differs from
  `inputs.component_id`, any input is missing, or the manifest the
  inputs would produce is not valid (`interface/data/SealedProvenance.md`
  — a bad `source_path`, `owners` entry, or hash, or a
  `verification_report` with no `criteria`, or an entry whose `result`
  is not `pass`, `fail`, or `skipped`, say), it MUST raise
  `InvalidSealedInputError` and write nothing, leaving any existing
  manifest untouched. Inputs are read with dual dict-or-attribute
  access (`R-PROV-014`), and the report's entries likewise
  (`R-PROV-016`).
