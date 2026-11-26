# Testing hotdocs-cli

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

Any stand-in llm-endpoint must provide `load_config`.
