# LLM Endpoint — Non-Functional Constraints

- **Determinism of dispatch, not of the response.** Backend resolution
  (`R-ENDPOINT-002`) MUST be a deterministic function of the model
  identifier; the backend's actual response content is explicitly not
  covered by that guarantee — same caveat `verifier-orchestrator`'s own
  constraints already state for `llm-judge`/`test_author` dispatch.
- **Network access, deliberately.** This is one of the few components in
  the corpus permitted to reach the network at all (alongside `generator`
  and `test-author` before this component existed) — every other
  component's "no network access" posture is unaffected and, if
  anything, easier to audit now that network access is concentrated in
  one place instead of three.
- **No retry-with-backoff, no unbounded wait.** See `R-ENDPOINT-004`.
- **Credential never leaves this component.** See `R-ENDPOINT-005`.
- **Idempotent dispatch is not claimed.** Unlike every `compiled` rule
  elsewhere in this corpus, calling `complete()` twice with identical
  arguments MAY return different `text` — caching that result, if a
  caller wants repeatability or cost control, is `cache-manager`'s job
  (via each caller's own cache key), not this component's.
