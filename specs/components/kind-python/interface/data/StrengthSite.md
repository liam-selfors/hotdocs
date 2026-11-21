# `StrengthSite`

```json
{"description": "pkg/__init__.py:2: n < 0 -> n >= 0", "file": "pkg/__init__.py", "index": 0}
```

A plain `dict` with exactly these three keys.

- `description`: `<file>:<line>: <before> -> <after>`, `<line>` the
  node's `lineno`, `<before>` and `<after>` `ast.unparse` of the node
  before and after the change.
- `file`: the Python file's relative path, as the code directory names
  it (`interface/library.md`).
- `index`: the site's position, from 0, among that file's sites.
