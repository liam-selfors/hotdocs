# Library

```
complete(prompt: str, model: str, *, backend=None, **params) -> ModelResponse
parse_model(model: str) -> tuple[str | None, str]
resolve_provider(model: str, config: dict | None = None) -> dict
DEFAULT_TIMEOUT_SECONDS = 600
```

`complete` returns a plain dict with exactly `ModelResponse`'s keys.
`parse_model` splits an identifier into `(provider, model)`, the provider
`None` for a bare name (`R-ENDPOINT-002`). `resolve_provider` returns
`{provider, model, base_url, api_key_env, timeout_seconds}` for an
identifier under `config` (`load_config`'s shape, or `None`), filling a
provider's defaults from `PROVIDERS` and `DEFAULT_TIMEOUT_SECONDS`; both
raise `ModelResolutionError` exactly where `R-ENDPOINT-002` says.

Not a pure function: it reaches a network (or the `claude` command).
`model` is `<provider>:<model>` or a bare name (`R-ENDPOINT-002`).
`**params` goes to the resolved backend: the HTTP providers understand
`max_tokens` and `temperature` (`ollama` also `num_ctx`) and ignore the
rest; `claude-cli` turns each into a command-line flag. A rejected
param is the provider's concern, surfaced as `model_call_error`
(`R-ENDPOINT-004`), not validated here.

`backend` (`D33`) — omitted, `complete()` resolves a real backend; a
caller supplying a callable `backend(prompt, model, **params) ->
ModelResponse` bypasses resolution, for testing dispatch,
classification, and logging against a mock, never a real call.

`PROVIDERS` holds exactly (`default_base_url`, `default_api_key_env`,
`suggested_model`): `claude-cli` (none, none, `claude-sonnet-5`),
`anthropic` (`https://api.anthropic.com`, `ANTHROPIC_API_KEY`,
`claude-sonnet-5`), `openai` (`https://api.openai.com/v1`,
`OPENAI_API_KEY`, `gpt-6-astra`), `openai-compatible` (none, none, `""`),
`gemini` (`https://generativelanguage.googleapis.com`, `GEMINI_API_KEY`,
`gemini-4-argon`), `ollama` (`http://localhost:11434`, none, `llama3.2`);
`needs_base_url` is true only for `openai-compatible`. None is `None`.

## Setup helpers (`R-ENDPOINT-007`, `R-ENDPOINT-009`)

```
PROVIDERS: dict[str, {default_base_url, default_api_key_env, needs_base_url, suggested_model}]
load_config(config_path: Path | None = None) -> dict | None
save_config(config_path: Path, provider: str, model: str, base_url: str | None = None,
            api_key_env: str | None = None, timeout_seconds: int | None = None) -> None
detect_providers(env: dict | None = None, probe_ollama: bool = True) -> list[dict]
check_connection(provider: str, model: str, base_url: str | None = None,
                 api_key_env: str | None = None, timeout_seconds: int = 30) -> dict
```

`load_config` returns `{provider, model, base_url, api_key_env,
timeout_seconds}` (unset entries `None`), or `None`; it raises
`ValueError` for an invalid file. `save_config` creates the file's
directory when missing and replaces only its `[llm]` table.
`detect_providers` returns, per
provider, `{provider, available, reason, suggested_model,
api_key_env}`; given `env`, only that dict supplies keys and `PATH`.
`check_connection` sends one prompt, with `max_tokens=1024` except to
`claude-cli`, and returns `{ok, error}`, `error` being `None` or
`{category, message}`; an unknown provider, or `openai-compatible`
without a `base_url`, raises `ValueError`. `ModelResolutionError` is
raised by `complete()` for `R-ENDPOINT-002`'s failures.
`resolve_backend_name(model)` is kept only for compatibility: it returns
`"anthropic"` for a bare `claude-*` name, the label the `claude`
command's backend had before there were several providers.

## HTTP, the call log, and config messages

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
