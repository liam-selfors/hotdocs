# Testing surface-checker

Asset criteria never use a real kind and never need Node. A test plants
each kind it names in its synthetic `repo_root`:

- `specs/architecture/asset-kind-<kind>.md`, any text (`check_surface` does not
  read it);
- `gen/kind-<kind>/kind_<kind>.py`, plain Python, for example

  ```python
  KIND = "fake"


  def surface(asset_file):
      return {"names": ["a", "b"]}
  ```

  plus `provision(repo_root)` returning
  `{"ok": True, "reason": "", "versions": {}, "lockfile_sha256": None}`;
  for `fakebad`, a `surface` whose body is `raise RuntimeError("boom")`;
  for `fakeoff`, the same `surface` and a `provision` returning `ok`
  `False` with `reason` `"fakeoff needs fakeprog >= 2"`.

Every synthetic `repo_root`, in every criterion, plants the `python`
adapter `gen/kind-python/kind_python.py`, so no criterion depends on the
tool's own:

```python
import sys
from pathlib import Path


def provision(repo_root):
    return {"ok": True, "reason": "", "versions": {}, "lockfile_sha256": None,
            "interpreter": sys.executable}
```

**The planted wrapper interpreter** is an executable file
`<repo_root>/pywrap` (mode `0o755`, POSIX shell) with the lines
`#!/bin/sh` and `HOTDOCS_WRAPPED=1 exec '<sys.executable>' "$@"`, the
test's own `sys.executable` written in; the planted `python` adapter's
`provision` then reports `"interpreter": str(Path(repo_root) / "pywrap")`.
A criterion whose `provision` reports `ok` `False` returns that `ok` and
`reason` with `"interpreter": None`.

A kind the criterion says has no adapter, such as `nokind_q`, is simply
not planted; no such kind exists under the tool's own `gen/` either.

The component's `component.md` frontmatter carries the criterion's
`assets:` line, for example

    ---
    id: comp-widget
    depends_on: []
    assets: [fake:static/app.js]
    ---

each asset file sits at `gen/widget/<path>` with any text, and each
interface file at `specs/components/widget/interface/assets/<file name>.md`
holds a heading and one fenced block whose lines state the names, for
example

    # app.js

    ```
    export function a(x)
    ```
