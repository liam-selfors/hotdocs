# R-ENDPOINT-004

**R-ENDPOINT-004** — MUST NOT retry a provider call, and MUST NOT leave
  one with an unbounded wait (`D7`). A call either succeeds, or fails within
  its provider's bounded timeout as a `model_call_error` with a
  `category` of exactly one of `network`/`auth`/`rate_limit`/`timeout`
  (`D20`; see `ModelResponse`), exactly once.

  **The bound MUST be at least 300 seconds** (`D34`) for a completion.
  Default 600;
  `timeout_seconds` in `hotdocs.toml` MAY raise it, never lower it below
  300. `check_connection` (`R-ENDPOINT-009`) is a probe, not a
  completion, and takes its own short bound.

  **HTTP providers** map a reply to a category: 401 or 403 `auth`; 429
  `rate_limit`; 408 or 504, and a socket timeout, `timeout`; any other
  non-2xx status, a connection failure, an unreadable body, or a reply
  with no text, `network`. `gemini` also maps a 400 whose body says the
  API key is not valid to `auth`. The `message` is a short static
  description: never the vendor's text, a header, or a credential
  (`R-ENDPOINT-005`). A provider that needs a key and finds none in the
  environment reports `auth` without making a call.
