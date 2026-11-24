# R-AUTHOR-030

**R-AUTHOR-030** — `author_test` MUST NOT read or write `cache-manager`,
  or keep any other store of authored tests: every call that gets as far
  as authoring makes at least one model call, none returns a stored
  test, and every result's `cache_hit` is `false`. Reusing a test is the
  caller's job, by the committed file and its header; where
  `specs/architecture/test-reuse.md` says "cached test" or "cached file"
  it means that committed file. A test a caller deleted as faulty is
  therefore always authored afresh, never restored (`D370`).
