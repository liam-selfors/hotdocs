# R-AUTHOR-028

**R-AUTHOR-028** — The test file `author_test` returns and writes MUST begin with the line
  `# hotdocs-criterion: sha256:<hex>`, `<hex>` the lowercase hex
  SHA-256, computed
  from the bundle and never taken from the model's content, that
  `specs/architecture/test-reuse.md`'s "The criterion header" defines
  (`D341`); the model's content follows on the
  next line. A first line of that content already beginning
  `# hotdocs-criterion:` is replaced, never repeated (`D320`).
