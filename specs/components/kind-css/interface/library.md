# Library

One module file, `kind_css.py`, never a package.

```
KIND: str           # "css"
GATE_VERSION: str   # "kind-css@1.0.0"
class AssetError(Exception)
layout_errors(asset_file: Path) -> list[str]
surface(asset_file: Path) -> dict
provision(repo_root: Path) -> ProvisionResult
asset_runner(asset_file: Path) -> Callable[[str, list], object]
strength_sites(asset_file: Path) -> list[StrengthSite]
apply_site(asset_file: Path, site: StrengthSite) -> None
guidance() -> dict  # {"generator": str, "test_author": str}
```

Implements: `specs/architecture/asset-kinds.md`, `specs/architecture/asset-kind-css.md`

`surface` returns `{"names": [str, ...]}`. `ProvisionResult` and
`StrengthSite` are plain `dict`s (`interface/data/`). Every path is a
`pathlib.Path`; `asset_file` is read as UTF-8 bytes decoded, with no
newline translation, and offsets count characters of that text.
