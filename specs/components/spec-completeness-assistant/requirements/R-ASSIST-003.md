# R-ASSIST-003

**R-ASSIST-003** — MUST produce a hint-mode preview for each component
  in the predicted blast radius — the original design's exact described
  use of hint mode, concretely implemented here for the first time.
  `spec-bundle-assembler` assembles each bundle in `hint` mode; with a
  `model` configured, `generator` then generates from it and that
  result is the preview. With no `model` (`R-ASSIST-007`), `generator`
  is never called — it cannot run without a model — and the preview is
  the hint-mode bundle itself (`D157`).
