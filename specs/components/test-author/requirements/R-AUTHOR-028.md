# R-AUTHOR-028

**R-AUTHOR-028** — The test file `author_test` returns and writes, on a
  cache hit as on a miss, MUST begin with the line
  `# hotdocs-criterion: sha256:<hex>`, `<hex>` the lowercase hex
  SHA-256, computed from the bundle and never taken from the model's
  content, of the bundle's `criterion_text`, a newline, and its
  `requirement_text`, encoded UTF-8; the model's content follows on the
  next line. A first line of that content already beginning
  `# hotdocs-criterion:` is replaced, never repeated (`D320`).
