# R-XMODEL-002

**R-XMODEL-002** — MUST call `generator` with the **same** `SpecBundle`
  (same `spec_bundle_hash`, cold mode) but a **different** model identifier,
  writing the result to an isolated location — never overwriting the
  canonical `gen/<component>/` tree.
