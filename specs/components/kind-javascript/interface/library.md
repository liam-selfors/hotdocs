# Library

One module file, `kind_javascript.py`, never a package.

```
KIND: str           # "javascript"
GATE_VERSION: str   # "kind-javascript@1.0.0"
class AssetError(Exception)
layout_errors(asset_file: Path) -> list[str]
surface(asset_file: Path) -> dict
provision(repo_root: Path) -> ProvisionResult
asset_runner(asset_file: Path) -> Callable[[str, list], object]
strength_sites(asset_file: Path) -> list[StrengthSite]
apply_site(asset_file: Path, site: StrengthSite) -> None
```

Implements: `specs/architecture/asset-kinds.md`, `specs/asset-kinds/javascript.md`

`surface` returns `{"names": [str, ...]}`. `ProvisionResult` and
`StrengthSite` are plain `dict`s (`interface/data/`). Every path is a
`pathlib.Path`; `asset_file` is read as UTF-8.

## Finding node

Every function that runs Node finds it as `shutil.which("node")` at call
time, so it follows `os.environ["PATH"]` as it is then. Every `node`
process gets the environment `{"PATH": os.environ.get("PATH", "")}` and
nothing else, captures stdout and stderr as text, and is killed after 30
seconds. Every temporary directory is `Path(tempfile.mkdtemp()).resolve()`
(resolved, because Node's permission model checks real paths) and is
removed before the function returns or raises.

## The scan

The scan reads the file's text left to right into tokens, each with its
character offset:

1. Whitespace is skipped.
2. `//` up to (not including) the next newline, and `/*` through the next
   `*/` (or the end of the file), are comments, skipped.
3. A `'`, `"` or `` ` `` starts a string token that ends at the next
   unescaped same quote, or the end of the file; a backslash makes the
   character after it part of the string. A template's `${...}` is
   inside its string.
4. A name token is `[A-Za-z_$][A-Za-z0-9_$]*`.
5. A number token is a digit followed by any of `[A-Za-z0-9_.]`.
6. Otherwise the longest of these operators that starts here is one
   token, else the single character is:
   `>>>=` `===` `!==` `>>>` `**=` `...` `<<=` `>>=` `&&=` `||=` `??=`
   `=>` `==` `!=` `<=` `>=` `&&` `||` `??` `++` `--` `+=` `-=` `*=`
   `/=` `%=` `&=` `|=` `^=` `**` `<<` `>>` `?.`

A `/` is always an operator: regular expression literals are not
recognised. A token's line is 1 plus the number of `\n` before its
offset.
