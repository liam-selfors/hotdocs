---
id: arch-llm-endpoint-http
title: llm-endpoint HTTP, Call Log and Config Messages
status: draft
owners: [pipeline-team]
depends_on: []
---

# llm-endpoint HTTP, Call Log and Config Messages

## Purpose

How `llm-endpoint`'s HTTP providers reach the network, what its call log
holds, and the wording of its configuration refusals, exactly as a test
observes them.

## Rules

Discovery reads `VAR_HOTDOCS_CONFIG` and the current directory; a
resolution test unsets the one and uses a fresh other.

Every HTTP request, the Ollama probe included, is
`urllib.request.urlopen(request, timeout=<seconds>)`, looked up on the
`urllib.request` module when the call is made (never imported by name,
so replacing `urllib.request.urlopen` reaches every call). The reply is
used only as a context manager and through `.read()`. Headers go into
`urllib.request.Request`, which stores names capitalized (`X-api-key`, `User-agent`),
so a recorded request's headers are read case-insensitively. An error status
arrives as `urllib.error.HTTPError` (its `code` and `read()`), a timeout
as `socket.timeout`, `TimeoutError` or a `URLError` wrapping one, and any
other failure as `URLError` or `OSError`. The Ollama probe requests
`<base_url>/api/tags` with a 1-second timeout and counts as available
whenever `urlopen` returns.

Each `complete()` call writes one JSON file under `.hotdocs/calls/` in
the current directory: `{"timestamp", "model", "backend", "text_present"}`
on success, `text_present` a boolean, or `{"timestamp", "model",
"backend", "model_call_error"}` on failure; `timestamp` is ISO 8601 UTC.

`complete()` raises `ModelResolutionError`, never `ValueError`, for an
invalid `hotdocs.toml`, and nothing else: an exception an injected
`backend` raises is returned as `model_call_error`, classified as HTTP
failures are (`HTTPError` 401 or 403 `auth`, 429 `rate_limit`, 408 or
504 or any timeout `timeout`, anything else `network`), with `text`
`null` and no retry. `load_config`'s message for an entry whose name
suggests a secret contains `must never hold a secret`; every refusal of an
`api_key_env` value contains `never the key itself`.
