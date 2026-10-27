# R-MERGE-004

**R-MERGE-004** — For a provenance miss on a **non-sealed** component
  (every sealed component is R-MERGE-015's job instead, unconditionally),
  MUST call `spec-bundle-assembler` then `generator` (cold
  mode, sample index 0) to produce a candidate, then `verifier-orchestrator`
  to check it — **wiring a real `test_author` callable (backed by
  `test-author`) and a real `judge` callable (backed by `llm-endpoint`,
  D30 — a `complete()` call, for `llm-judge`-kind criteria) into that
  call.** This
  component is where those two injectable parameters actually get their
  real implementations in production; nothing upstream of this requirement
  assigned who does that wiring, so it's stated explicitly here rather than
  left implicit.

  **Neither real function matches the required single-`bundle`-argument
  shape** (glossary's "Injected `judge`/`test_author` callable shape,"
  `D82`): both `llm_endpoint.complete` and `test_author.author_test`
  require a `model` argument with no default, among others. This
  component MUST wrap each in a closure capturing `model`/`seed`/
  `llm_backend`/`repo_root` itself — the only layer with a model
  identifier to capture.
