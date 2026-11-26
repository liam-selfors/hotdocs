# Library

The importable module is `test_supply` (`gen/test-supply/test_supply.py`).

```
supply(component_id: str, criterion_id: str, repo_root: Path, *, test_author=None, interpreter: str | None = None, assets: list[str] = (), drivers: list[str] = ()) -> SuppliedTest
discard(component_id: str, criterion_id: str, repo_root: Path) -> None
```

`test_author` is the glossary's "Injected `judge`/`test_author` callable
shape" (`D65`): one `bundle` argument, returning a
`TestAuthoringResult`-shaped mapping or object (`model`, `seed`,
`prompt_version`, `cache_hit`, `model_call_error`, `file`); only
`model_call_error` and `file["content"]` are read. `assets` are the
component's declared asset paths and `drivers` its declared drivers'
fixture names, both passed to `test-probe`'s `probe`.

The committed test is the glossary's "Criterion test filename" (`D63`)
directly under `<repo_root>/verification/<slug>/generated-test/`.

It loads `spec-bundle-assembler` from
`<repo_root>/gen/spec-bundle-assembler/` and `test-probe` from
`<repo_root>/gen/test-probe/`, each else from the tool root, the parent
of the nearest `gen` directory above this module's own file (`D199`).

Implements: `specs/architecture/test-reuse.md`
