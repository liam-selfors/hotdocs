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

Every `.py` file under the code directory, outside `__pycache__`, MUST
parse with `ast.parse` under the environment's Python. `layout_errors`
returns, for each file that does not, in sorted relative-path order,
`<relative path>:<line>: SyntaxError: <message>`, `<message>` the
exception's `msg`; an empty list means the layout is valid. That the
module itself exists is the generator's own `missing_module` check.

## Environment

Python, version from `<interpreter> -c "import platform;
print(platform.python_version())"`. A project that commits
`environments/python/requirements.lock` gets an environment of its own:
`provision` creates `<repo_root>/.hotdocs/env/python/` with
`<running interpreter> -m venv` if its interpreter is absent, installs the lock with
`<env python> -m pip install --no-input --disable-pip-version-check -r <lock>`
(pip's version notice would otherwise end its stderr) when the lock's
SHA-256 differs from the one recorded in
`<repo_root>/.hotdocs/env/python/.lock-sha256` (then records it), and
reports `interpreter` the environment's `bin/python` (`Scripts\python.exe`
on Windows). The lock MUST pin `pytest`, since criteria run under it.
With no lock, the environment is the one `hotdocs` runs in:
`interpreter` is the running interpreter, `lockfile_sha256` null, and
nothing is created; the `hotdocs` corpus itself has no lock. Failures:
`python environment: requirements.lock does not pin pytest`, and
`python environment: <last non-empty line of the failing command's
stderr>` when creating or installing fails.

## Surface

The public top-level names of `<module>`: `surface(code_dir)["names"]`
is the sorted list of `dir(<module>)` entries not starting with `_`,
read by importing it in a subprocess of the environment's interpreter
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
outside `__pycache__`, in sorted relative-path order, is parsed once;
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
