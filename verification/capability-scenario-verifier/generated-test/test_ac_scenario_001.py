import json
from pathlib import Path

import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_capability_scenario_result_keyed_by_capability_not_component(tmp_path):
    repo_root = tmp_path / "repo"

    _write(
        repo_root / "specs" / "components" / "alpha" / "component.md",
        """---
id: comp-alpha
title: Alpha Component
status: ratified
owners: [lselfors]
realizes: [P-FOO]
sealed: false
last_ratified_commit: 0000000
---

# comp-alpha

Alpha component for testing.
""",
    )
    _write(repo_root / "gen" / "alpha" / "alpha.py", "# alpha placeholder\n")

    _write(
        repo_root / "specs" / "components" / "beta" / "component.md",
        """---
id: comp-beta
title: Beta Component
status: ratified
owners: [lselfors]
realizes: [P-FOO]
sealed: false
last_ratified_commit: 0000000
---

# comp-beta

Beta component for testing.
""",
    )
    _write(repo_root / "gen" / "beta" / "beta.py", "# beta placeholder\n")

    _write(
        repo_root / "specs" / "product" / "foo.md",
        """---
id: P-FOO
title: Foo Capability
status: ratified
owners: [lselfors]
last_ratified_commit: 0000000
---

# P-FOO: Foo Capability

### CS-FOO-001

Covers: P-FOO
Kind: generated-test

```gherkin
Given a widget
When the widget is used
Then the widget works
```
""",
    )

    log_path = tmp_path / "test_author_calls.log"

    def fake_test_author(bundle):
        scenario_id = _get(bundle, "scenario_id")
        with open(log_path, "a") as f:
            f.write(json.dumps({"scenario_id": scenario_id}) + "\n")
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-FOO/generated-test/test_cs_foo_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }

    blast_radius = ["comp-alpha", "comp-beta"]

    report = capability_scenario_verifier.run_capability_scenarios(
        blast_radius, repo_root, test_author=fake_test_author
    )

    assert "comp-alpha" not in report
    assert "comp-beta" not in report
    assert "P-FOO" in report
    assert len(report) == 1

    entry = report["P-FOO"]
    assert _get(entry, "overall") == "pass"

    scenarios = _get(entry, "scenarios")
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert _get(scenario, "id") == "CS-FOO-001"
    assert _get(scenario, "kind") == "generated-test"
    assert _get(scenario, "result") == "pass"

    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    recorded = json.loads(lines[0])
    assert recorded["scenario_id"] == "CS-FOO-001"