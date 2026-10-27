# R-GEN-016

**R-GEN-016** — In `hint` mode (`bundle.hint_code` is not `null`),
  `generate()` MUST NOT write to `gen/<component>/` or to
  `cache-manager` — it returns the candidate (or cache hit) in the
  `GenerationResult` only. Reading the cache (`R-GEN-005`) is
  unaffected.

  Two independent reasons, not just a style preference: (1) a
  hint-mode preview runs speculatively, before a change is submitted
  (`R-ASSIST-003`), and must never overwrite the real, verified
  `gen/<component>/`; (2) `spec_bundle_hash` excludes `hint_code`
  (`spec-bundle-assembler` `R-ASSEMBLE-007`), so a `hint`- and
  `cold`-mode call for the same spec state share one cache key —
  writing a hint-informed candidate there could let a later `cold`
  build, which must see no prior code (`R-GEN-001`, `D1`), silently
  reuse it.

  Reading a cache hit in `hint` mode stays safe: a hit only exists for
  a hash already matching some committed state, so reuse is correct
  and fast. Only a *write* can contaminate a future cold build.
