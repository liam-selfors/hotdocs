# R-GATE-002

**R-GATE-002** — On a miss, MUST call `spec-bundle-assembler` then
  `generator` (cold mode) to produce a candidate, then, if it has
  files, `verifier-orchestrator` to check it — passing a `test_author`
  closure backed by `test-author` and a `judge` closure backed by
  `llm-endpoint` (`R-GATE-010`), each of the glossary's
  single-`bundle`-argument shape (`D65`).

  This component does its own wiring (`D86`): nothing calls it with
  closures already built, so its own `model`/`seed`/`llm_backend` are
  the only place a model identifier enters. Each closure captures
  them, exactly as `interface/library.md` states.
