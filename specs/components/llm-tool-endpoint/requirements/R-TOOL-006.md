# R-TOOL-006

**R-TOOL-006** — A failed HTTP request MUST end the loop with `stop`
  `error` and a `model_call_error` categorized as `llm-endpoint`'s
  `R-ENDPOINT-004` does: status 401 or 403 `auth`; 429 `rate_limit`; 408
  or 504, and a socket timeout, `timeout`; any other non-2xx status, a
  connection failure, or a body that is not the provider's JSON reply,
  `network`. The `message` is a short static description, never the
  vendor's text, a header or a key. No request is ever retried.
