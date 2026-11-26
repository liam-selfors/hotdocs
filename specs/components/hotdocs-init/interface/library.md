# Library

```
run(argv, *, tool_root, input_fn=None, output_fn=None, env=None, cwd=None) -> int
main(argv: list[str] | None = None) -> int
```

`main` is the `cli-conventions.md` entry: it returns `run(argv,
tool_root=<tool root>)`, `None` meaning `sys.argv[1:]`, the tool root being
the parent of the nearest directory named `gen` above this module's own
file. `run` is the injectable form `hotdocs-cli` calls (`R-INIT-007`).

For both, `argv` is everything after the word `init`. `input_fn` defaults to `input`,
`output_fn` to `print`, `env` to `os.environ`, `cwd` to the current
directory. Normal messages go to `output_fn`, errors to `sys.stderr`.
Each question is passed to `input_fn` as its text plus one trailing space,
e.g. `"Save anyway? [y/N] "`.
`tool_root` is the tool's own repository. `init` copies nothing from it but
`examples/slugify/`, only with `--example`, to the project root, never under
`examples/`; it reads `requirements.txt` (`R-INIT-003`) and `pyproject.toml`
(`R-INIT-002`) and loads `llm-endpoint` from it.

## llm-endpoint

Loaded from `<tool_root>/gen/llm-endpoint/llm_endpoint.py`, or when that
file is absent the package `llm_endpoint/__init__.py` there. Exactly these
names are used, read with dual dict-or-attribute access:

- `PROVIDERS` — `{provider: {default_base_url, default_api_key_env,
  needs_base_url, suggested_model}}`; `suggested_model` is `""` for
  `openai-compatible`;
- `detect_providers(env=None, probe_ollama=True)` — one entry per provider,
  `{provider, available, reason, suggested_model, api_key_env}`; called with
  `env=<the env given to run>`, and with no `env` when none was given;
- `check_connection(provider, model, base_url=None, api_key_env=None,
  timeout_seconds=30, auth=None)` — `{ok, error}`, `error` `None` or `{category,
  message}`; raises `ValueError` for an unknown provider or a missing
  required `base_url`;
- `save_config(config_path, provider, model, base_url=None,
  api_key_env=None, timeout_seconds=None, auth=None)` — keeps other file content,
  replaces `[llm]`, raises `ValueError` for anything invalid;
- `load_config(config_path=None)` — `{provider, model, base_url,
  api_key_env, timeout_seconds, auth}`, `None` when there is no `[llm]` table,
  `ValueError` when invalid.

`hotdocs.toml` is written and read only through `save_config` and
`load_config`. Any stand-in must provide all five names.

Implements: `specs/architecture/cli-conventions.md`, `specs/architecture/tool-version.md`
