---
id: arch-mutation-runs
title: Mutation Runs
status: draft
owners: [pipeline-team]
depends_on: []
---

# Mutation Runs

## Purpose

How `verifier-orchestrator` runs a component's generated tests against
mutants (`R-VERIFY-006`, `R-VERIFY-014`), so that a mutant's run sees
the same layout as the criterion run and a score is only ever computed
from tests that pass on the unmutated code (`D324`).

## Rules

**The tests.** Mutation runs use the `generated-test` files of the
criteria whose `result` is `pass`, and no other file. With no such file,
no baseline or mutant runs.

**The sandbox.** A fresh temporary directory `<tmp>` holds
`<tmp>/gen/<slug>/`, a copy of `<repo_root>/gen/<slug>/` without
`__pycache__`, and, for every other directory `<repo_root>/gen/<name>/`,
a symbolic link `<tmp>/gen/<name>` to it. Only files of the copy are
ever mutated. Each run's working directory is `<tmp>/gen/<slug>`, its
`PYTHONPATH` that directory then the plugin directory (below), with
pytest's `--noconftest`. So code that finds
its dependencies from its own `__file__` (the parent of the nearest
`gen` directory, then `gen/<dependency-slug>/`) reaches the same
dependency code it reaches in the criterion run.

**Language outside an asset.** Whenever a baseline would run, before
it, every `.py` file of
the copy, outside `__pycache__`, in order of relative path compared as
`/`-joined strings, is parsed and its `str` constants are
read in `ast.walk` order, including each part of an f-string and never
a docstring (the first statement of a module, class or function body).
The first constant at least 200 characters long that matches
`\bfunction\s*[\w$]*\s*\(|=>|\b(const|let)\s` and contains `;` or `{`
holds JavaScript no mutant reaches: no baseline or mutant runs,
`mutation_score` is `null`, `overall` is `fail`, and `mutation_error`
is exactly

    javascript in a string at <file>:<line>; declare it as an asset (specs/architecture/asset-kinds.md)

with `<file>` the file's path relative to `<tmp>/gen/<slug>/`, using
`/`, and `<line>` the constant's `lineno` (issue #13, `D343`).

**The baseline.** Before any mutant, and even when there is none, the
tests run once on the unmutated copy, with the 300-second timeout. If that run passes, each
mutant's timeout is 2 seconds or 10 times the baseline's own run time,
whichever is larger. If it exits nonzero or times out, no mutant runs:
`mutation_score` is `null`, `overall` is `fail`, and the report's
`mutation_error` is exactly one of

    mutation baseline failed in the sandbox: pytest exited <code>
    mutation baseline timed out in the sandbox after 300 seconds

with `<code>` pytest's exit status. `mutation_error` is `null` in every case
this document does not name.

**The `asset_runner` plugin.** Every baseline and mutant run gets the
plugin `specs/architecture/verifier-fixtures.md` describes, its asset
files those of the copy, `<tmp>/gen/<slug>/<path>`.

**The sites.** Each site gives exactly one mutant, applied alone to the
copy, in this order:

- *Python* (`D159`, `D172`, `D344`): the sites the `python` adapter,
  `comp-kind-python` found by asset-kinds.md's Lookup, lists with
  `strength_sites(<tmp>/gen/<slug>)`, in that order; each mutant is
  `apply_site(<tmp>/gen/<slug>, site)`. The rules, every `.py` file of
  the copy in order of relative path compared as `/`-joined strings,
  and Python's operator swaps, are
  `specs/architecture/asset-kind-python.md`'s "Strength check", stated
  there exactly as this document stated them before `D344`.
- *Assets* (`specs/architecture/asset-kinds.md`, `D343`): after every
  Python site come, for each asset the component declares, in
  declaration order, the sites the kind's adapter lists with
  `strength_sites(<tmp>/gen/<slug>/<path>)`, in that order. Each gives
  one mutant: `apply_site(<tmp>/gen/<slug>/<path>, site)`.

For every mutant, the tests run, then every file of the copy is
restored to its original bytes before the next mutant.

**An adapter failure.** When a kind's `strength_sites` or `apply_site`
raises, `python`'s included, no further mutant runs, `mutation_score`
is `null`, `overall` is `fail`, and `mutation_error` is exactly

    <kind> adapter failed: <ExceptionType>: <message>

with `<ExceptionType>` the exception's class `__name__` and `<message>`
its `str()`.

**The interpreter.** The baseline and every mutant run under the
`interpreter` the `python` adapter's `provision` reported for this
`verify` call (`D344`), never `sys.executable` unless that is what it
reported.

**The score.** Killed mutants over all mutants, Python and asset alike,
one score for the component (`D124`), `1.0` when there are no mutants;
a mutant is killed when its run exits nonzero or times out.

Test fixtures: a fixture making a component's code load a dependency
by path writes the dependency as `<repo_root>/gen/<dependency-slug>/<module>.py`
and has the component's module load it from
`Path(__file__).resolve().parents[1] / "<dependency-slug>" / "<module>.py"`.
The criterion run's working directory is `repo_root` and the sandbox's
is not, so a cached test asserting `(Path.cwd() / "specs").is_dir()`
passes its criterion and fails the baseline.
