---
id: arch-asset-kind-python
title: Asset kind python
status: draft
owners: [pipeline-team]
depends_on: []
---

# Asset kind `python`

The component's own Python code: its module `<module>.py` or package
`<module>/` and every other `.py` file under `gen/<slug>/`, `<module>`
the slug with hyphens replaced by underscores (`D344`). Every component
has this asset implicitly; it is never declared in `assets`. Its asset
file is the component's code directory itself: `gen/<slug>/`, a
candidate's, or the mutation sandbox's copy. `comp-kind-python` is its
adapter.

## Layout

The code directory's **Python files** are every `.py` file under it,
at any depth, outside `__pycache__`, always taken sorted by their
relative paths compared as `/`-joined strings (`b.py` before `b/c.py`).
Each MUST parse with `ast.parse`, run in the adapter's own process,
under `hotdocs`' Python, not the environment's: a syntax check needs no
environment. `layout_errors` returns, for each file that does not, in
that order, `<relative path>:<line>: SyntaxError: <message>`,
`<message>` the exception's `msg` (`<line>` 0 when it has none; a
`ValueError` from the parse counts too, its `str` the message); an empty
list means the layout is valid, and it never raises. That the
module itself exists is the generator's own `missing_module` check.

## Environment

Python. `versions` is `{"python": <platform.python_version()>,
"packages": "sha256:<hex>"}`, both read by running the reported
interpreter with `-I` and a fixed program (`comp-kind-python`), the
packages hash over the environment's installed distributions as sorted,
distinct `<normalized name>==<version>` lines joined with `\n`, so a
package nobody declared counts too (`D345`). A project may pin its
interpreter in `environments/python/python-version`: its stripped text
is a version prefix (`3.14` or `3.14.6`), and the running interpreter's
full version must equal it or start with it followed by `.`, else
`provision` fails with `python environment: needs Python <pin>, found
<version>` before anything is created, with or without a lock (a lock's
environment is built from the running interpreter). A project that commits
`environments/python/requirements.lock` gets an environment of its own:
`provision`, holding an exclusive lock on
`<repo_root>/.hotdocs/env/python.lock` (`fcntl.flock`; POSIX only, no
lock where `fcntl` is missing), rebuilds `<repo_root>/.hotdocs/env/python/`
with `<running interpreter> -m venv --clear` and installs the lock with
`<env python> -m pip install --no-input --disable-pip-version-check -r <lock>`
(pip's version notice would otherwise end its stderr) whenever the
environment's interpreter is missing or not executable, or the marker
`<repo_root>/.hotdocs/env/python/.lock-sha256` does not record both the
lock's SHA-256 and the running interpreter's full version (then
records them), and reports `interpreter` the environment's `bin/python` (`Scripts\python.exe`
on Windows). The lock MUST pin `pytest`, since criteria run under it.
With no lock, the environment is the one `hotdocs` runs in:
`interpreter` is the running interpreter, `lockfile_sha256` null, and
nothing is created; the `hotdocs` corpus itself has no lock. Failures:
`python environment: requirements.lock does not pin pytest`, and
`python environment: <last non-empty line of the failing command's
stderr>` when creating or installing fails.

`surface` and `asset_runner` take no `repo_root`, so they start the
interpreter the environment variable `HOTDOCS_PYTHON` names, when set
and non-empty, else the running one; `verifier-orchestrator` sets it to
`provision`'s `interpreter` for runs that use them (nothing in the
pipeline calls either today).

## Surface

The public top-level names of `<module>`: `surface(code_dir)["names"]`
is the sorted list of `dir(<module>)` entries not starting with `_`,
read by importing it in a subprocess of the environment's interpreter (`## Environment`)
with `PYTHONPATH` the code directory. The interface's `library.md` is
the asset's interface file; `surface-checker`'s import and dependency
checks (`R-SURF-001`, `R-SURF-002`) remain the surface gate for this
kind.

## Running criteria

Generated tests import the module directly, as every Python criterion
always has; they never use `asset_runner` for it. `asset_runner(code_dir)`
returns `run(entry, args)`, which imports `<module>` in a new subprocess
of the environment's interpreter with `PYTHONPATH` the code directory,
calls `entry` with `args` spread, and returns the JSON-encoded result
decoded, raising `AssetError` with the exception's message when it
raises.

## Strength check

Mutation, exactly as `specs/architecture/mutation-runs.md` has always
stated Python's (`D159`, `D172`): every `.py` file of the code directory,
outside `__pycache__`, in the order `## Layout` states, is parsed once;
within a file, sites are taken in `ast.walk` order. A comparison with
exactly one operator has it swapped `==`↔`!=`, `<`↔`>=`, `>`↔`<=`,
`is`↔`is not`, `in`↔`not in`; an `and`/`or` is flipped to the other; a
binary `+`↔`-`, `*`↔`/`, `//`↔`%`; a boolean constant is negated. Never
a numeric constant, a chained comparison or anything else. Each site is
`{"description": "<relative path>:<line>: <before> -> <after>", "file":
<relative path>, "index": <position among that file's sites>}`, `before`
and `after` the node's `ast.unparse` text; `apply_site` writes the whole
file back with `ast.unparse` of the tree with that one change.

## Test author guidance

None of its own: `test-author`'s rules and `model-reply-format.md` carry
Python's test conventions, so `guidance()["test_author"]` is `""`.

## Generator guidance

None of its own: `specs/architecture/generator-prompt.md` carries
Python's conventions, so `guidance()["generator"]` is `""`.
