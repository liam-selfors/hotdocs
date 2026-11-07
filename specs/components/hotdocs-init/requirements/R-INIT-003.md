# R-INIT-003

**R-INIT-003** — After setup, `init` MUST check prerequisites and report each missing one through `output_fn` (never stderr), as the two lines below, never running a command, in this order:

  - Python 3.10 or newer: `missing: Python 3.10 or newer` / `  fix: install Python 3.10 or newer`;
  - each `name==version` line of `<tool_root>/requirements.txt` whose distribution is not installed (`importlib.metadata.version(name)` raises `PackageNotFoundError`; a module name never stands in, since `PyYAML` installs `yaml`): `missing: <that line>` / `  fix: pip install -r <tool_root>/requirements.txt`, with the path exactly as `tool_root` was given;
  - `claude` not found on `env["PATH"]` (as `shutil.which("claude", path=env.get("PATH"))` finds it: an executable file), checked only when the provider is `claude-cli` (the one chosen in this run, or, when the provider step did not run, the one `load_config(<dir>/hotdocs.toml)` returns): `missing: claude on PATH` / `  fix: install Claude Code and sign in`.

With any missing, `init` returns `3`, after finishing everything else.
