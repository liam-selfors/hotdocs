import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "pipeline" / "criterion-compiler"))
import criterion_compiler  # noqa: E402


WIDGET_LIBRARY_MD = """# Library

```
do_the_thing(x) -> Result
process(args) -> Result
bar_get(key) -> str
```
"""

WIDGET_RESULT_DATA_MD = """# `Result`

```json
{
  "value": 1,
  "owner": "alice"
}
```
"""


def write_component(repo_root: Path, name: str, criteria: dict[str, tuple[str, str, str]], *, library_md: str = WIDGET_LIBRARY_MD, data_files: dict[str, str] | None = None) -> Path:
    """Writes specs/components/<name>/{acceptance/*.md,interface/...} under
    repo_root. `criteria` maps criterion_id -> (covers, kind, gherkin_body)."""
    comp_dir = repo_root / "specs" / "components" / name
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface" / "data").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface" / "library.md").write_text(library_md, encoding="utf-8")
    for fname, content in (data_files or {"Result.md": WIDGET_RESULT_DATA_MD}).items():
        (comp_dir / "interface" / "data" / fname).write_text(content, encoding="utf-8")

    for criterion_id, (covers, kind, gherkin_body) in criteria.items():
        text = f"# {criterion_id}\n\nCovers: {covers}\nKind: {kind}\n\n```gherkin\n{gherkin_body}\n```\n"
        (comp_dir / "acceptance" / f"{criterion_id}.md").write_text(text, encoding="utf-8")
    return comp_dir


@pytest.fixture
def repo_root(tmp_path):
    return tmp_path
