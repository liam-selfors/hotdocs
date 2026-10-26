# R-ENDPOINT-003

**R-ENDPOINT-003** — v1 MUST implement exactly one backend (Anthropic,
  via `VAR-ANTHROPIC-API-KEY`, resolved by a plain process-environment
  lookup — see that var's own spec for the resolution mechanism and its
  Pro-plan-vs-API-billing precedence caveat, `D46`) — no OpenAI/open-model
  backend, and no
  backend-plugin/registry machinery, built in now for vendors nothing in
  this corpus actually calls yet (same anti-premature-abstraction
  reasoning `D18` applied to `criterion-compiler`'s single emit target).
  A future backend MUST be addable as a new implementation behind
  `R-ENDPOINT-002`'s existing resolve/dispatch split, never a redesign of
  the public `complete()` contract (`R-ENDPOINT-001`) or of any caller.
