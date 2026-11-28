# Library

The importable module is `mutation_scorer`
(`gen/mutation-scorer/mutation_scorer.py`).

```
score(component_id: str, repo_root: Path, tests: list[str], environment: RunEnvironment) -> MutationResult
```

`tests` are absolute paths of the test files to score with, in order.
`environment` is `run-environment`'s `prepare(component_id, repo_root)`
result with `ok` true: every run uses its `interpreter`,
`pytest_args()`, its `plugin_dir` last on `PYTHONPATH`, and
`env_for(<the sandbox copy>)`. The declared assets are its `assets`
after the first (`python`) entry; each kind's adapter is found by
`specs/architecture/asset-kinds.md`'s Lookup, the tool root being the
parent of the nearest directory named `gen` above this module's own
file.

Implements: `specs/architecture/mutation-runs.md`, `specs/architecture/asset-kinds.md`, `specs/architecture/run-environment.md`
