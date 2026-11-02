# Library

```
complete(prompt: str, model: str, *, backend=None, **params) -> ModelResponse
```

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
`ValueError` for an invalid file. `detect_providers` returns, per
provider, `{provider, available, reason, suggested_model,
api_key_env}`; given `env`, only that dict supplies keys and `PATH`.
`check_connection` returns `{ok, error}`, `error` being `None` or
`{category, message}`; an unknown provider, or `openai-compatible`
without a `base_url`, raises `ValueError`. `ModelResolutionError` is
raised by `complete()` for `R-ENDPOINT-002`'s failures.
`resolve_backend_name(model)` is kept only for compatibility: it returns
`"anthropic"` for a bare `claude-*` name, the label the `claude`
command's backend had before there were several providers.
