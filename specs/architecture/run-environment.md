---
id: arch-run-environment
title: Run Environment
status: draft
owners: [pipeline-team]
depends_on: [arch-asset-kinds, arch-test-drivers]
---

# Run Environment

## Purpose

How every pytest run of a component's or capability's tests, criterion,
baseline or mutant, reaches its declared assets and test drivers
(`specs/architecture/asset-kinds.md`, `specs/architecture/test-drivers.md`,
`D383`). `comp-run-environment` provisions them once per verification and
writes the plugin; its callers add the plugin to each run.

## The plugin

Each `prepare` call writes a fresh temporary directory `<plug>` holding
only `hotdocs_run_plugins.py`. Every run that uses it gets
`-p hotdocs_run_plugins`, `<plug>` as the last `PYTHONPATH` entry, and
the environment variables `HOTDOCS_ASSETS` and `HOTDOCS_DRIVERS`, each a
JSON list:

- `HOTDOCS_ASSETS`: one object per declared asset, in declaration order,
  `{"path": <declared path>, "file": <absolute path of that asset in the code being verified>, "adapter": <absolute path of the kind's adapter module>}`,
  `[]` when none. The code being verified is `gen/<slug>/` for a
  criterion run and the mutation sandbox's copy for a mutation run.
- `HOTDOCS_DRIVERS`: one object per declared driver, sorted by name,
  `{"name": <name>, "fixture": <the adapter's FIXTURE>, "adapter": <absolute path of the driver's adapter module>, "repo_root": <absolute repo_root>}`,
  `[]` when none.

The plugin imports nothing from `hotdocs` and defines:

- the function-scoped fixture `asset_runner`, a function of one `path`.
  It reads `HOTDOCS_ASSETS` when the fixture is requested; for the entry
  whose `path` equals it, it loads the module at `adapter` with
  `importlib.util.spec_from_file_location` and returns
  `module.asset_runner(Path(file))`; any other `path` raises `KeyError`
  with the message
  `asset_runner: <repr of path> is not a declared asset (declared: <each entry's path, joined by ", ", or none>)`
  (`D369`).
- for each `HOTDOCS_DRIVERS` entry, read when the plugin is imported, a
  function-scoped fixture named its `fixture`, taking pytest's
  `tmp_path`: it loads the module at `adapter` the same way, yields
  `module.open_session(Path(repo_root), tmp_path)`, and calls the
  session's `close()` at teardown, also when the test failed.

A test using a fixture of a driver not declared errors at setup, as for
any unknown fixture.

## Timeouts

Every run's timeout kills "the whole process tree": that is every process descended
from the run, found by walking parent links (`ps -eo pid=,ppid=` or the
platform's equivalent) when the timeout fires and killed before the run
itself. Killing the run's process group is not enough: a descendant
that started its own session, as a nested verification does, leaves
the group and outlives the run, busy, with no parent.
