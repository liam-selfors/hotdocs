# Library

```
TOOL_VERSION = "0.1.0"
main(argv=None, *, tool_root=None, input_fn=None, output_fn=None,
     env=None, cwd=None) -> int
```

`argv` defaults to `sys.argv[1:]`, `input_fn` to `input`, `output_fn` to
`print`, `env` to `os.environ`, `cwd` to the current directory. Normal
messages go to `output_fn`, errors to `sys.stderr`. `tool_root` is the tool's
own repository, supplied by the entry module in `tools/`; when `None`, it is
the parent of the nearest `gen` directory above this module's file. A
project holds only its own components, so every verb falls back to it
(`R-CLI-001`). The forwarded tokens end with `--repo-root=<root>` unless
the arguments already hold a `--repo-root` (`R-CLI-002`), followed only by
an injected `--model=...` (`R-CLI-003`).

## llm-endpoint

Found as any module is (`R-CLI-001`). The one name
used is `load_config(config_path=None)` — `{provider, model, base_url,
api_key_env, timeout_seconds}`, `None` when there is no `[llm]` table,
`ValueError` when invalid. Any stand-in must provide it.

## Test fixtures

A **fake component** at `<project>/<dir>/<module>.py` defines `main(argv)`,
which appends `json.dumps(argv)` as a line to `<project>/calls.log` (the path
written into its source) and returns `7`. For the `init` row the fake lives
at `<tool_root>/gen/hotdocs-init/hotdocs_init.py` and also logs the keyword
arguments it received. A **fake tool root** is a separate temporary
directory passed as `tool_root`, holding fakes at the same relative paths.

Implements: `specs/architecture/cli-conventions.md`
