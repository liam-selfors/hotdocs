# R-AUTHOR-019

**R-AUTHOR-019** — The call to `llm_endpoint.complete()` MUST pass
  only `prompt`, `model`, and `backend` — mirroring `generator`'s own
  call exactly — and MUST NOT forward `seed` or any other bookkeeping
  parameter: `complete()` forwards every param to the real backend,
  where `seed` fails the call (`D108`). `seed` is recorded in the result only.
