# R-LINT-027

**R-LINT-027** — Every `` `<file>`'s "<Section>" section `` pointer in a
  live document MUST resolve: the file MUST exist, and MUST contain a
  heading matching `<Section>` exactly. Catches a cross-reference going
  stale when either side changes — the file moves, or the section it
  names is renamed — without a human noticing.
