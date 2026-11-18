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
ever mutated. Each run's working directory and `PYTHONPATH` are
`<tmp>/gen/<slug>`, with pytest's `--noconftest`. So code that finds
its dependencies from its own `__file__` (the parent of the nearest
`gen` directory, then `gen/<dependency-slug>/`) reaches the same
dependency code it reaches in the criterion run.

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

**The score.** Killed mutants over all mutants, `1.0` when there are no
mutants; a mutant is killed when its run exits nonzero or times out.

Test fixtures: a fixture making a component's code load a dependency
by path writes the dependency as `<repo_root>/gen/<dependency-slug>/<module>.py`
and has the component's module load it from
`Path(__file__).resolve().parents[1] / "<dependency-slug>" / "<module>.py"`.
The criterion run's working directory is `repo_root` and the sandbox's
is not, so a cached test asserting `(Path.cwd() / "specs").is_dir()`
passes its criterion and fails the baseline.
