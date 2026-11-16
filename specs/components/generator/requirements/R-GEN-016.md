# R-GEN-016

**R-GEN-016** — In `hint` mode (`bundle.hint_code` is not `null`),
  `generate()` MUST NOT write to `gen/<component>/`, and `commit_cache`
  MUST NOT write a hint-mode result to `cache-manager` — `generate` returns the candidate (or cache hit) in the
  `GenerationResult` only. Reading the cache (`R-GEN-005`) is
  unaffected.

  A hint-informed candidate written to the shared cache key could be
  reused by a later `cold` build, which must see no prior code
  (`R-GEN-001`).
