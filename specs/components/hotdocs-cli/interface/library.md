# Library

```
TOOL_VERSION = "0.1.0"
main(argv=None, *, tool_root=None, input_fn=None, output_fn=None,
     env=None, cwd=None) -> int
```

`argv` defaults to `sys.argv[1:]`, `input_fn` to `input`, `output_fn` to
`print`, `env` to `os.environ`, `cwd` to the current directory. Normal
messages go to `output_fn`, errors to `sys.stderr`. `tool_root` is the tool's
own repository, supplied by the entry module in `tools/`; only the `init`
verb uses it.

## llm-endpoint

Loaded from `<repo root>/gen/llm-endpoint/llm_endpoint.py`. The one name
used is `load_config(config_path=None)` — `{provider, model, base_url,
api_key_env, timeout_seconds}`, `None` when there is no `[llm]` table,
`ValueError` when invalid. Any stand-in must provide it.

## Test fixtures

A **fake component** at `<project>/<dir>/<module>.py` defines `main(argv)`,
which appends `json.dumps(argv)` as a line to `<project>/calls.log` (the path
written into its source) and returns `7`. For the `init` row the fake lives
at `<tool_root>/gen/hotdocs-init/hotdocs_init.py` and also logs the keyword
arguments it received.
