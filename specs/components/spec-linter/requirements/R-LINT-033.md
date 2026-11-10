# R-LINT-033

**R-LINT-033** — `lint` MUST include, after its own findings and as
  `Finding`s, every finding `citation-checker`'s and then
  `size-checker`'s `check(repo_root)` returns, limited to `paths` the
  same way as its own (`D242`). `load_corpus` MUST be `corpus-loader`'s
  function itself.
