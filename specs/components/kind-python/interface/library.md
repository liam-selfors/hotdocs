# Library

One module file, `kind_python.py`, never a package.

```
KIND: str           # "python"
GATE_VERSION: str   # "kind-python@1.0.0"
class AssetError(Exception)
layout_errors(asset_file: Path) -> list[str]
surface(asset_file: Path) -> dict
provision(repo_root: Path) -> ProvisionResult
asset_runner(asset_file: Path) -> Callable[[str, list], object]
strength_sites(asset_file: Path) -> list[StrengthSite]
apply_site(asset_file: Path, site: StrengthSite) -> None
guidance() -> dict  # {"generator": str, "test_author": str}
```

Implements: `specs/architecture/asset-kinds.md`, `specs/architecture/asset-kind-python.md`

`surface` returns `{"names": [str, ...]}`. `ProvisionResult` and
`StrengthSite` are plain `dict`s (`interface/data/`). Every path is a
`pathlib.Path`.

## The code directory

For this kind `asset_file` is a directory, the component's code
directory (`gen/<slug>/`, a candidate's or a sandbox copy). Its
**Python files** are every `*.py` file under it, at any depth, whose
path relative to it has no part named `__pycache__`, each named by that
relative path written with `/` and taken in ascending order of those
strings (so `b.py` comes before `b/c.py`). Its **module** is the
directory's own name with every `-` replaced by `_`: `<module>.py` or
the package `<module>/` inside it.

## The interpreter

The Python that `surface` and `asset_runner` start is the `interpreter`
of the most recent `provision` call in this process that reported `ok`,
or `sys.executable` before any. Each such subprocess gets a copy of
`os.environ` with `PYTHONPATH` set to `str(asset_file)` alone, runs with
the code directory as its working directory, captures stdout and stderr
as text, and is killed after 30 seconds. Its result is read from the
last stdout line that is not empty after stripping, decoded as JSON.
