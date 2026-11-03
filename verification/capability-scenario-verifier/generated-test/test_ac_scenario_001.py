import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _keys(obj):
    if isinstance(obj, dict):
        return list(obj.keys())
    if hasattr(obj, "__dict__"):
        return list(vars(obj).keys())
    return []


COMPONENT_MD = """---
id: comp-{slug}
title: {title}
status: draft
owners: [lselfors@gmail.com]
realizes: [P-WIDGET]
sealed: false
---

# {title}

Purpose: a fixture component for AC-SCENARIO-001.
"""

CAPABILITY_MD = """---
id: P-WIDGET
title: Widget Capability
status: draft
owners: [lselfors@gmail.com]
---

# Widget Capability

### CS-WIDGET-001

Covers: P-WIDGET
Kind: generated-test

```gherkin
Given a widget
When it is used
Then it works
```
"""


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_generated_test_scenario_keyed_by_capability_id(tmp_path):
    repo_root = tmp_path / "repo"

    _write(
        repo_root / "specs" / "components" / "alpha" / "component.md",
        COMPONENT_MD.format(slug="alpha", title="Alpha Component"),
    )
    _write(
        repo_root / "specs" / "components" / "beta" / "component.md",
        COMPONENT_MD.format(slug="beta", title="Beta Component"),
    )
    _write(repo_root / "gen" / "alpha" / "alpha.py", "# fixture component code\n")
    _write(repo_root / "gen" / "beta" / "beta.py", "# fixture component code\n")
    _write(repo_root / "specs" / "product" / "widget.md", CAPABILITY_MD)

    call_log = tmp_path / "test_author_calls.log"

    def fake_test_author(bundle):
        with open(call_log, "a") as f:
            f.write(str(_get(bundle, "scenario_id", "")) + "\n")
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-WIDGET/generated-test/test_cs_widget_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-alpha", "comp-beta"], repo_root, test_author=fake_test_author
    )

    assert call_log.exists()
    assert "CS-WIDGET-001" in call_log.read_text()

    keys = _keys(report)
    assert "P-WIDGET" in keys
    assert "comp-alpha" not in keys
    assert "comp-beta" not in keys

    capability_entry = _get(report, "P-WIDGET")
    assert _get(capability_entry, "overall") == "pass"

    scenarios = _get(capability_entry, "scenarios")
    assert len(scenarios) == 1

    scenario = scenarios[0]
    assert _get(scenario, "id") == "CS-WIDGET-001"
    assert _get(scenario, "kind") == "generated-test"
    assert _get(scenario, "result") == "pass"