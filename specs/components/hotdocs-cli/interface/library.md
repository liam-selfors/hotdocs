# Library

```
run(argv=None, *, tool_root=None, input_fn=None, output_fn=None,
    env=None, cwd=None) -> int
main(argv: list[str] | None = None) -> int
```

`main` is the `cli-conventions.md` entry: it returns `run(argv)`, so the
tool root is derived as below. `run` is the injectable form, called by the
entry module in `tools/` and by every criterion (`R-CLI-006`).

The tool version printed by `R-CLI-004` is read from `tool_root` as
`specs/architecture/tool-version.md` says; the module holds no version
literal.

`argv` defaults to `sys.argv[1:]`, `input_fn` to `input`, `output_fn` to
`print`, `env` to `os.environ`, `cwd` to the current directory. Normal
messages go to `output_fn`, errors to `sys.stderr`. `tool_root` is the tool's
own repository, supplied by the entry module in `tools/` to `run`; when `None`, it is
the parent of the nearest `gen` directory above this module's file. The forwarded tokens end with `--repo-root=<root>` unless
the arguments already hold a `--repo-root` (`R-CLI-002`), followed only by
an injected `--model=...` (`R-CLI-003`). Without a `--repo-root`
argument the repo root is `cwd` made absolute (`os.path.abspath`, not
resolved), and that string is what `--repo-root=<root>` carries; no
marker file such as `hotdocs.toml` or `.git` is needed.

## llm-endpoint

Found and loaded as any module is (`R-CLI-001`): under the repo root
first, fresh on every call, so a test may change a fake between calls.
It is consulted only for a `required` or `optional` row. The one name
used is `load_config(config_path=None)` — `{provider, model, base_url,
api_key_env, timeout_seconds}`, `None` when there is no `[llm]` table,
`ValueError` when invalid.

Implements: `specs/architecture/cli-conventions.md`, `specs/architecture/tool-version.md`
