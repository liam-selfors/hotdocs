# R-GATE-002

**R-GATE-002** — For a provenance miss on a non-sealed component (every
  sealed component is `R-GATE-007`'s job instead, unconditionally),
  MUST call `spec-bundle-assembler` then `generator` (cold mode, sample
  index 0) to produce a candidate, then `verifier-orchestrator` to
  check it — passing straight through the real `test_author`/`judge`
  callables this component receives as its own `run_component_gates`
  parameters, already wired to the required single-`bundle`-argument
  shape (glossary's "Injected `judge`/`test_author` callable shape,"
  `D65`) by the caller.

  **This component never does the wiring itself.** `merge-orchestrator`
  is the only layer with a model identifier to capture (`model`/`seed`/
  `llm_backend`/`repo_root`), and it already independently needs the
  same closures for its own `capability-scenario-verifier` call
  (`R-MERGE-014`) — centralizing the one wiring site there, rather than
  duplicating it here, is the point of splitting this component out
  this way (`D76`).
