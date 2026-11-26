# Testing generator

**Assets.** A criterion about assets plants, under its temporary
`repo_root`, `specs/components/widget-maker/component.md`, written
exactly as shown with `---` in column 0 of line 1:

```
---
id: comp-widget-maker
title: Widget Maker
status: draft
owners: [pipeline-team]
depends_on: []
sealed: false
assets: [fake:static/app.txt]
---

# Widget Maker
```

replacing `fake` with the criterion's kind when it names another, and
the fake kind: its definition `specs/architecture/asset-kind-fake.md`, a `# Fake`
line and the seven `## ` sections of `specs/architecture/asset-kinds.md`
each followed by a line `x`, and its adapter
`gen/kind-fake/kind_fake.py`:

```python
from pathlib import Path

KIND = "fake"


def layout_errors(asset_file):
    return ["bad"] if "bad" in Path(asset_file).read_text(encoding="utf-8") else []


def provision(repo_root):
    if (Path(repo_root) / "NO_ENV").exists():
        return {"ok": False, "reason": "fake needs fakeprog >= 2", "versions": {}, "lockfile_sha256": None}
    return {"ok": True, "reason": "", "versions": {"fakeprog": "2.0.0"}, "lockfile_sha256": None}
```

Every criterion's temporary `repo_root` also plants the fake `python`
adapter `gen/kind-python/kind_python.py` (`D344`), so no criterion
depends on the real adapter or environment:

```python
from pathlib import Path

KIND = "python"


def layout_errors(code_dir):
    return ["bad.py:1: SyntaxError: x"] if (Path(code_dir) / "bad.py").exists() else []


def provision(repo_root):
    return {"ok": True, "reason": "", "versions": {"python": "3.12"}, "lockfile_sha256": None, "interpreter": "/fake/python"}
```

To observe that `provision` is called, a criterion rewrites it to also
append a line to a file outside `repo_root` whose path is written into
the source, and the fake kind's likewise.

A kind named `nosuchkind` has neither, here or in the tool, so it has no
adapter. No Node or other program is needed.

**Mock replies.** A mock model reads the nonce as
`re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)` and
builds its reply in `interface/library.md`'s reply format; "a reply
with blocks for" some files ends in the `END REPLY` line.

**The cache.** With `VAR_CACHE_STORE_URL` unset, a test inspects the
cache with `cache_manager.get(key, repo_root=repo_root)` or
`cache_manager.stats(repo_root=repo_root)`; a test MAY build a
`GenerationResult` by keyword.

All criteria are `generated-test`, with an injected mock model.
