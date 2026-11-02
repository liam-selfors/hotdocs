# LLM Endpoint — Non-Functional Constraints

- **Determinism of dispatch, not of the response.** Resolution
  (`R-ENDPOINT-002`) MUST be a deterministic function of the model
  identifier and the configuration; the backend's actual response content is explicitly not
  covered by that guarantee — same caveat `verifier-orchestrator`'s own
  constraints already state for `llm-judge`/`test_author` dispatch.
- **Network access, deliberately.** This is one of the few components in
  the corpus permitted to reach the network at all (alongside `generator`
  and `test-author` before this component existed) — every other
  component's "no network access" posture is unaffected and, if
  anything, easier to audit now that network access is concentrated in
  one place instead of three.
- **No retry-with-backoff, no unbounded wait.** See `R-ENDPOINT-004`.
- **Credential never leaves this component, and never reaches a file.**
  See `R-ENDPOINT-005`; `hotdocs.toml` names a variable, never holds a key.
- **No new dependency.** The HTTP providers use the standard library only.
- **Idempotent dispatch is not claimed.** Unlike every `compiled` rule
  elsewhere in this corpus, calling `complete()` twice with identical
  arguments MAY return different `text` — caching that result, if a
  caller wants repeatability or cost control, is `cache-manager`'s job
  (via each caller's own cache key), not this component's.
- **The call log (`R-ENDPOINT-006`) is a local write side effect, not a
  gate input.** `.hotdocs/calls/` follows the same boundary `.hotdocs/
  tracking/` already does (`SPEC_GUIDELINES.md` §1) — never read by any
  gate's pass/fail decision, purely for a human or analytical tool to
  query afterward.
