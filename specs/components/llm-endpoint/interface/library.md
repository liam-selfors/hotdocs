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
`{provider, model, base_url, api_key_env, timeout_seconds, auth}` for an
identifier under `config` (`load_config`'s shape, an entry it lacks
read as `None`, or `None`), filling a
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
            api_key_env: str | None = None, timeout_seconds: int | None = None,
            auth: str | None = None) -> None
detect_providers(env: dict | None = None, probe_ollama: bool = True) -> list[dict]
check_connection(provider: str, model: str, base_url: str | None = None,
                 api_key_env: str | None = None, timeout_seconds: int = 30,
                 auth: str | None = None) -> dict
```

`load_config` returns `{provider, model, base_url, api_key_env,
timeout_seconds, auth}` (unset entries `None`), or `None`; it raises
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

In `specs/architecture/llm-endpoint-http.md`; the `claude` command in
`specs/architecture/claude-cli-adapter.md`.

Implements: `specs/architecture/claude-cli-adapter.md`, `specs/architecture/llm-endpoint-http.md`
