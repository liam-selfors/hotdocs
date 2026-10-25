# R-ENDPOINT-004

**R-ENDPOINT-004** — MUST NOT implement retry-with-backoff around a
  backend call, and MUST NOT configure a backend's SDK/HTTP client with
  an unbounded wait — the same posture `D21`/`R-GEN-011` already
  established for `generator`, now owned at the layer that actually
  touches the network rather than restated by every caller. A call either
  succeeds, or fails within its backend's own bounded timeout, reported
  as `model_call_error` (network, auth, rate-limit, or timeout — the
  vocabulary `R-GEN-008` originally defined, owned here now) exactly once
  — no internal attempt loop. Recovery from a `model_call_error` stays
  one layer up, same as before (re-running the merge, `R-MERGE-017`), not
  this component's job.

  **This promise is only as strong as each configured backend's own
  bound.** v1's one backend (Anthropic) already has this property, which
  is why `D21` could rely on it. A future backend (`R-ENDPOINT-003`)
  MUST provide an equivalent bounded guarantee itself — if a vendor or a
  self-hosted model has no such guarantee natively, that backend's own
  implementation MUST impose one (e.g. a client-side timeout), so this
  component's contract to every caller stays uniform regardless of which
  backend is configured. Not resolved generically here, because no
  second backend exists yet to resolve it against.
