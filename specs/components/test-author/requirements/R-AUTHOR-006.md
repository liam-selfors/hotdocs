# R-AUTHOR-006

**R-AUTHOR-006** — Output MUST be written only under
  `verification/<component>/generated-test/` — never under `gen/` (it is a
  test, not application code), and never overwriting `criterion-compiler`'s
  own output directory. The filename itself MUST be the glossary's
  "Criterion test filename" formula (`D63`) — never a content hash or
  any other suffix — since `verifier-orchestrator` must be able to
  predict this exact path to check for an already-authored test before
  deciding whether to dispatch to this component at all (`R-VERIFY-002`).
