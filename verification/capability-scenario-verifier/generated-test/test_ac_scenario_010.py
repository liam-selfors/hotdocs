import json
import os
from pathlib import Path

import pytest

import capability_scenario_verifier


FOO_COMPONENT_MD = """---
id: comp-foo
title: Foo Component
status: draft
owners: [tester]
realizes: [P-X]
sealed: false
---

# comp-foo

Component foo realizes P-X.
"""

BAR_COMPONENT_MD = """---
id: comp-bar
title: Bar Component
status: draft
owners: [tester]
realizes: [P-X]
sealed: false
---

# comp-bar

Component bar realizes P-X.
"""

CAPABILITY_MD = """---
id: P-X
title: Capability X
status: draft
owners: [tester]
---

# Capability X

CAPABILITY_BODY_MARKER_TEXT_12345

### CS-X-001

Covers: P-X
Kind: generated-test

```gherkin
Given a widget
When it is tested
Then it passes
```
"""

FAKE_TEST_AUTHOR_MODULE = """
import json
import os


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    record = {
        "model": model,
        "seed": seed,
        "repo_root": str(repo_root),
        "llm_backend": llm_backend,
        "bundle": bundle,
    }
    log_path = os.environ["CAPTURE_LOG"]
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\\n")
    return {
        "model_call_error": None,
        "file": {
            "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
            "content": "def test_x():\\n    assert True\\n",
        },
    }
"""


def _build_repo(repo_root: Path) -> None:
    foo_dir = repo_root / "specs" / "components" / "foo"
    bar_dir = repo_root / "specs" / "components" / "bar"
    (foo_dir / "interface").mkdir(parents=True)
    (bar_dir / "interface").mkdir(parents=True)
    (foo_dir / "component.md").write_text(FOO_COMPONENT_MD)
    (bar_dir / "component.md").write_text(BAR_COMPONENT_MD)
    (foo_dir / "interface" / "library.md").write_text("FOO_IFACE")
    (bar_dir / "interface" / "library.md").write_text("BAR_IFACE")

    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "gen" / "bar").mkdir(parents=True)
    (repo_root / "gen" / "foo" / "__init__.py").write_text("")
    (repo_root / "gen" / "bar" / "__init__.py").write_text("")

    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True)
    (product_dir / "P-X.md").write_text(CAPABILITY_MD)

    (repo_root / "specs" / "glossary.md").write_text("GLOSS")

    test_author_dir = repo_root / "gen" / "test-author"
    test_author_dir.mkdir(parents=True)
    (test_author_dir / "test_author.py").write_text(FAKE_TEST_AUTHOR_MODULE)


def test_run_capability_gates_builds_capability_bundle_and_calls_author_test(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    log_path = tmp_path / "author_test_calls.jsonl"
    os.environ["CAPTURE_LOG"] = str(log_path)

    sentinel_backend = "sentinel-backend-7f3a2c91"

    capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=3, llm_backend=sentinel_backend
    )

    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])

    assert record["model"] == "m"
    assert record["seed"] == 3
    assert record["repo_root"] == str(repo_root)
    assert record["llm_backend"] == sentinel_backend

    bundle = record["bundle"]

    assert bundle["component_id"] == "capabilities/P-X"
    assert bundle["criterion_id"] == "CS-X-001"
    assert bundle["covers"] == "P-X"
    assert bundle["criterion_text"].strip() == (
        "Given a widget\nWhen it is tested\nThen it passes"
    )
    assert "CAPABILITY_BODY_MARKER_TEXT_12345" in bundle["requirement_text"]
    assert bundle["glossary"] == "GLOSS"
    assert bundle["dependency_interfaces"] == {}
    assert bundle["module_names"] == ["bar", "foo"]

    interface_text = bundle["interface"]
    idx_bar_header = interface_text.find("## comp-bar")
    idx_bar_iface = interface_text.find("BAR_IFACE")
    idx_foo_header = interface_text.find("## comp-foo")
    idx_foo_iface = interface_text.find("FOO_IFACE")

    assert -1 not in (idx_bar_header, idx_bar_iface, idx_foo_header, idx_foo_iface)
    assert idx_bar_header < idx_bar_iface < idx_foo_header < idx_foo_iface