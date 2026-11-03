import json
import tempfile
from pathlib import Path

import capability_scenario_verifier


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_ac_scenario_010():
    repo_root = Path(tempfile.mkdtemp())

    capability_md = """---
id: P-X
title: Capability P-X
status: draft
owners: [lselfors@gmail.com]
---

# Capability P-X

This capability provides widget functionality end to end.

### CS-X-001

Covers: P-X
Kind: generated-test

```gherkin
Given a widget
When it is used
Then it works
```
"""
    _write_file(repo_root / "specs/product/P-X.md", capability_md)

    foo_component_md = """---
id: comp-foo
title: Foo Component
status: draft
owners: [lselfors@gmail.com]
sealed: true
source_path: pipeline/foo/
realizes: [P-X]
---

# Foo Component

Purpose: fake foo component for testing.
"""
    _write_file(repo_root / "specs/components/foo/component.md", foo_component_md)
    _write_file(
        repo_root / "specs/components/foo/interface/library.md",
        "# Foo Interface\n\nFOO_IFACE\n",
    )

    bar_component_md = """---
id: comp-bar
title: Bar Component
status: draft
owners: [lselfors@gmail.com]
sealed: true
source_path: pipeline/bar/
realizes: [P-X]
---

# Bar Component

Purpose: fake bar component for testing.
"""
    _write_file(repo_root / "specs/components/bar/component.md", bar_component_md)
    _write_file(
        repo_root / "specs/components/bar/interface/library.md",
        "# Bar Interface\n\nBAR_IFACE\n",
    )

    _write_file(repo_root / "specs/glossary.md", "GLOSS")

    record_dir = Path(tempfile.mkdtemp())
    record_path = record_dir / "test_author_calls.jsonl"

    fake_test_author_template = '''
import json

RECORD_PATH = "__RECORD_PATH__"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    record = {
        "model": model,
        "seed": seed,
        "repo_root": str(repo_root),
        "llm_backend_id": id(llm_backend),
        "bundle": bundle,
    }
    with open(RECORD_PATH, "a") as f:
        f.write(json.dumps(record) + "\\n")
    return {
        "model_call_error": None,
        "file": {
            "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
            "content": "def test_x():\\n    assert True\\n",
        },
    }
'''
    fake_test_author_content = fake_test_author_template.replace(
        '"__RECORD_PATH__"', repr(str(record_path))
    )
    _write_file(repo_root / "gen/test-author/test_author.py", fake_test_author_content)

    sentinel_backend = object()

    capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=3, llm_backend=sentinel_backend
    )

    assert record_path.exists(), "author_test was never invoked"
    lines = [line for line in record_path.read_text().splitlines() if line.strip()]
    assert len(lines) == 1, f"expected author_test called once, got {len(lines)}"
    record = json.loads(lines[0])

    assert record["model"] == "m"
    assert record["seed"] == 3
    assert record["repo_root"] == str(repo_root)
    assert record["llm_backend_id"] == id(sentinel_backend)

    bundle = record["bundle"]
    assert bundle["component_id"] == "capabilities/P-X"
    assert bundle["criterion_id"] == "CS-X-001"
    assert bundle["covers"] == "P-X"
    assert bundle["criterion_text"].strip() == (
        "Given a widget\nWhen it is used\nThen it works"
    )
    assert (
        "This capability provides widget functionality end to end."
        in bundle["requirement_text"]
    )
    assert bundle["glossary"].strip() == "GLOSS"
    assert bundle["dependency_interfaces"] == {}

    interface = bundle["interface"]
    idx_bar_header = interface.find("## comp-bar")
    idx_bar_iface = interface.find("BAR_IFACE")
    idx_foo_header = interface.find("## comp-foo")
    idx_foo_iface = interface.find("FOO_IFACE")

    assert idx_bar_header != -1
    assert idx_bar_iface != -1
    assert idx_foo_header != -1
    assert idx_foo_iface != -1
    assert idx_bar_header < idx_bar_iface < idx_foo_header < idx_foo_iface