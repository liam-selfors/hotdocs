# Library

The importable module is `run_environment`
(`gen/run-environment/run_environment.py`).

```
prepare(component_id: str, repo_root: Path) -> RunEnvironment
prepare_capability(capability_id: str, repo_root: Path) -> RunEnvironment
```

`prepare` reads `<repo_root>/specs/components/<slug>/component.md`
frontmatter: its `assets` line as `specs/architecture/asset-kinds.md`
reads it and its `drivers` line as `specs/architecture/test-drivers.md`
reads it. `prepare_capability` reads the `drivers` line of the
`specs/product/*.md` whose frontmatter `id` is `capability_id`; it
declares no assets.

Adapters are found by each document's Lookup, the tool root being the
parent of the nearest directory named `gen` above this module's own
file, and loaded by path afresh on every call, with
`sys.dont_write_bytecode` true while it loads so no `__pycache__` is
written beside it.

Implements: `specs/architecture/asset-kinds.md`, `specs/architecture/test-drivers.md`, `specs/architecture/run-environment.md`
