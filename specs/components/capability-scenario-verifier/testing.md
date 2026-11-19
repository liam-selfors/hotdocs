# Testing capability-scenario-verifier

Every synthetic `repo_root` in which a test is run plants the `python`
adapter `gen/kind-python/kind_python.py`, so no criterion depends on the
tool's own:

```python
import sys


def provision(repo_root):
    return {"ok": True, "reason": "", "versions": {}, "lockfile_sha256": None,
            "interpreter": sys.executable}
```

**The planted wrapper interpreter** is an executable file
`<repo_root>/pywrap` (mode `0o755`, POSIX shell) with exactly the lines

    #!/bin/sh
    HOTDOCS_WRAPPED=1 exec '<sys.executable>' "$@"

the test's own `sys.executable` written in, and the planted adapter's
`provision` returns `"interpreter": str(Path(repo_root) / "pywrap")`
(with `from pathlib import Path`). A `provision` that reports `ok`
`False` returns
`{"ok": False, "reason": "python environment: no lock", "versions": {},
"lockfile_sha256": None, "interpreter": None}`.
