# R-GEN-004

**R-GEN-004** — The model identifier MUST be an explicit parameter, never
  hardcoded to "the canonical pin" — this is the single mechanism that lets
  `cross-model-divergence-checker` call this same component with a second
  model rather than reimplementing generation. Credential resolution MUST
  follow the model identifier, not a fixed assumption of which vendor is in
  play — this is why `uses_var` lists both `VAR-ANTHROPIC-API-KEY` and
  `VAR-SECOND-MODEL-API-KEY` rather than only the former: found as a gap
  while specifying `cross-model-divergence-checker`, which needs this
  component to actually be able to authenticate to a second vendor, not
  just accept its identifier as a string.
