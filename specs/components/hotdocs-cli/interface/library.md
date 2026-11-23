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
the parent of the nearest `gen` directory above this module's file. A
project holds only its own components, so every verb falls back to it
(`R-CLI-001`). The forwarded tokens end with `--repo-root=<root>` unless
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
`ValueError` when invalid. Any stand-in must provide it.

## Test fixtures

A **fake component** at `<project>/<dir>/<module>.py` defines `main(argv)`,
which appends `json.dumps(argv)` as a line to `<project>/calls.log` (the path
written into its source) and returns `7`. For the `init` row the fake lives
at `<tool_root>/gen/hotdocs-init/hotdocs_init.py` and defines `run(argv,
**keywords)` in place of `main`, also logging the keywords it received. A
**fake usage component** is a fake component that, after logging, prints
to stderr the two lines `usage error: unknown argument` and
`usage: fake [options]`, and returns `2`. A **fake tool root** is a separate temporary
directory passed as `tool_root`, holding fakes at the same relative paths
and, where a criterion says so, a `pyproject.toml`.
A **fake llm-endpoint** at `<project>/gen/llm-endpoint/llm_endpoint.py`
defines `load_config(config_path=None)`, whose behaviour (return a dict,
return `None`, or raise `ValueError`) is written into its source. A
project is a temporary directory passed as `cwd`.

Implements: `specs/architecture/cli-conventions.md`, `specs/architecture/tool-version.md`
