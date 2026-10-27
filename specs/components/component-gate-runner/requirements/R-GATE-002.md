# R-GATE-002

**R-GATE-002** — For a provenance miss on a non-sealed component, MUST
  call `spec-bundle-assembler` then `generator` (cold mode, sample
  index 0) to produce a candidate, then `verifier-orchestrator` to
  check it — wiring the real `test_author` callable (backed by
  `test-author`) and a real `judge` callable (backed by `llm-endpoint`,
  a `complete()` call for `llm-judge`-kind criteria) into that call,
  both built to the glossary's "Injected `judge`/`test_author`
  callable shape" (single-`bundle`-argument, `D65`).

  **This component does its own wiring** (`D86`): it is invoked
  directly by a developer, not called by anything else with its own
  wiring already done, so `model`/`seed`/`llm_backend`/`repo_root` —
  its own CLI/library parameters — are the only place a model
  identifier is captured for this call. Neither `llm_endpoint.complete`
  nor `test_author.author_test` matches the required
  single-`bundle`-argument shape itself (both need a `model` argument
  with no default, among others); this component wraps each in a
  closure capturing its own `model`/`seed`/`llm_backend` before passing
  it to `verifier-orchestrator`.
