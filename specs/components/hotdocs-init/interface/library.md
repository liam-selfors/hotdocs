# Library

```
main(argv, *, tool_root, input_fn=None, output_fn=None, env=None, cwd=None) -> int
```

`argv` is everything after the word `init`. `input_fn` defaults to `input`,
`output_fn` to `print`, `env` to `os.environ`, `cwd` to the current
directory. Normal messages go to `output_fn`, errors to `sys.stderr`.
Each question is passed to `input_fn` as its text plus one trailing space,
e.g. `"Save anyway? [y/N] "`.
`tool_root` is the tool's own repository: the source of everything `init`
vendors (`gen/`, `pipeline/`; `examples/slugify/` only with `--example`,
to the project root, never under `examples/`), plus `requirements.txt`,
which `init` only reads (`R-INIT-003`) and never copies.

## llm-endpoint

Loaded from `<project>/gen/llm-endpoint/llm_endpoint.py`. Exactly these
names are used, read with dual dict-or-attribute access:

- `PROVIDERS` — `{provider: {default_base_url, default_api_key_env,
  needs_base_url, suggested_model}}`; `suggested_model` is `""` for
  `openai-compatible`;
- `detect_providers(env=None, probe_ollama=True)` — one entry per provider,
  `{provider, available, reason, suggested_model, api_key_env}`; called with
  `env=<the env given to main>`, and with no `env` when none was given;
- `check_connection(provider, model, base_url=None, api_key_env=None,
  timeout_seconds=30)` — `{ok, error}`, `error` `None` or `{category,
  message}`; raises `ValueError` for an unknown provider or a missing
  required `base_url`;
- `save_config(config_path, provider, model, base_url=None,
  api_key_env=None, timeout_seconds=None)` — keeps other file content,
  replaces `[llm]`, raises `ValueError` for anything invalid;
- `load_config(config_path=None)` — `{provider, model, base_url,
  api_key_env, timeout_seconds}`, `None` when there is no `[llm]` table,
  `ValueError` when invalid.

`hotdocs.toml` is written and read only through `save_config` and
`load_config`. Any stand-in must provide all five names.

## Test fixtures

A **fake tool root** holds `gen/<slug>/<module>.py` fakes for a few slugs,
among them `llm-endpoint` (fakes of the five names above that also log each
call to a file outside both the project and the tool root, so a log never counts as a change to either), `pipeline/criterion-compiler/criterion_compiler.py`,
`examples/slugify/specs/product/slugs.md`, and a `requirements.txt` whose only line is
`pytest==` plus `importlib.metadata.version("pytest")` (so nothing is missing). A test embeds no secret-shaped string.
