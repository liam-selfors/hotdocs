# R-AUTHOR-019

**R-AUTHOR-019** — The call to `llm_endpoint.complete()` MUST pass
  only `prompt`, `model`, and `backend` — mirroring `generator`'s own
  call exactly — and MUST NOT forward `seed` or any other bookkeeping
  parameter. `complete()` forwards every param verbatim to the real
  backend (`R-ENDPOINT-001`), which turns each into a CLI flag; `seed`
  is not a real flag, so forwarding it fails every real (non-mocked)
  call outright. `seed` is `author_test`'s own cache-key input only.

  Found once a real retry ran for the first time (`D108`): all 14
  criteria failed identically with a generic backend error.
