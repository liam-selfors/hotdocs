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
a symbolic link `<tmp>/gen/<name>` to it, and, when
`<repo_root>/specs/asset-kinds/` exists, a symbolic link
`<tmp>/specs/asset-kinds` to it, so the tool root's asset-kind
definitions (`specs/architecture/asset-kinds.md`) are those of the
criterion run. Only files of the copy are
ever mutated. Each run's working directory is `<tmp>/gen/<slug>`, its
`PYTHONPATH` that directory then the plugin directory (below), with
pytest's `--noconftest`. So code that finds
its dependencies from its own `__file__` (the parent of the nearest
`gen` directory, then `gen/<dependency-slug>/`) reaches the same
dependency code it reaches in the criterion run.

**Language outside an asset.** Whenever a baseline would run, before
it, every `.py` file of
the copy, in sorted path order, is parsed and its `str` constants are
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

with `<code>` pytest's exit status. `mutation_error` is `null` in every
other case.

**The `asset_runner` plugin.** Every baseline and mutant run gets the
plugin `specs/architecture/verifier-fixtures.md` describes, its asset
files those of the copy, `<tmp>/gen/<slug>/<path>`.

**The sites.** Every `.py` file of the copy, in sorted path order, is
parsed once; within a file, sites are taken in `ast.walk` order, and
each site gives exactly one mutant, a copy of the file with that one
change, written back with `ast.unparse`.

- *Python* (`D159`, `D172`): a comparison with exactly one operator
  (a chained comparison is not a site) has it swapped `==`↔`!=`,
  `<`↔`>=`, `>`↔`<=`, `is`↔`is not`, `in`↔`not in`; an `and`/`or` is
  flipped to the other; a binary `+`↔`-`, `*`↔`/`, `//`↔`%`; a boolean
  constant is negated. Never a numeric constant or anything else.
- *Assets* (`specs/architecture/asset-kinds.md`, `D343`): after every
  Python site come, for each asset the component declares, in
  declaration order, the sites the kind's adapter lists with
  `strength_sites(<tmp>/gen/<slug>/<path>)`, in that order. Each gives
  one mutant: `apply_site(<tmp>/gen/<slug>/<path>, site)` rewrites the
  copy's asset file with that one change, the tests run, and the file's
  original bytes are written back before the next mutant.

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
