# R-AUTHOR-020

**R-AUTHOR-020** — `author_test` MUST validate every extracted test with
  `test-probe`'s `probe(content, bundle, module_name)`, `content` the
  extracted file as extracted, without `R-AUTHOR-028`'s header, and
  `module_name` the component's slug with hyphens replaced by
  underscores, never relying on the model's self-check alone and
  applying no other check before it. A test whose `ProbeReport` has `ok`
  false is rejected: it goes to the repair loop (`R-AUTHOR-027`) and is
  never cached or written as it stands.
