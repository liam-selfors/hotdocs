# R-GEN-016

**R-GEN-016** — In `hint` mode (`bundle.hint_code` is not `null`),
  `generate()` MUST NOT write to `gen/<component>/`, and `commit_cache`
  MUST NOT write a hint-mode result to `cache-manager`; it returns the candidate (or cache hit) only. Reading the
  cache (`R-GEN-005`) is unaffected.
