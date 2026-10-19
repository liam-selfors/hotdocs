# R-GEN-004

**R-GEN-004** — The model identifier MUST be an explicit parameter, never
  hardcoded to "the canonical pin." Credential resolution MUST follow the
  model identifier actually passed, not a fixed assumption of which vendor
  is in play.

  **Second-vendor credential resolution is currently moot, not resolved
  away:** `uses_var` lists only `VAR-ANTHROPIC-API-KEY` for this build —
  `VAR-SECOND-MODEL-API-KEY` was added here, then removed, specifically
  because every caller that would pass this component a second vendor's
  model identifier (`cross-model-divergence-checker`, and `test-author`'s
  own second-model preference) is itself deferred for now; see
  `cross-model-divergence-checker/component.md`'s build-status note. The
  "explicit parameter, never hardcoded" rule above is unaffected either
  way — it was never specific to supporting a second vendor, it's what
  single-model operation with a swappable pin already requires. If a
  second-vendor caller returns, this is additive: re-add
  `VAR-SECOND-MODEL-API-KEY` to `uses_var`, no change to the parameter
  contract itself.
