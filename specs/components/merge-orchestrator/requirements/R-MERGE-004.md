# R-MERGE-004

**R-MERGE-004** — For a cache miss on a **non-sealed** component (a sealed
  component's cache miss is R-MERGE-015's job instead — the two are
  mutually exclusive and jointly exhaustive over every component in the
  blast radius), MUST call `spec-bundle-assembler` then `generator` (cold
  mode, sample index 0) to produce a candidate, then `verifier-orchestrator`
  to check it — **wiring a real `test_author` callable (backed by
  `test-author`) and a real `judge` callable (a direct call to the
  configured model, for `llm-judge`-kind criteria) into that call.** This
  component is where those two injectable parameters actually get their
  real implementations in production; nothing upstream of this requirement
  assigned who does that wiring, so it's stated explicitly here rather than
  left implicit.
