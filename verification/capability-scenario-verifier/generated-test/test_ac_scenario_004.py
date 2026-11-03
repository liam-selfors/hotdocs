import dataclasses
import json

import capability_scenario_verifier


COMPONENT_MD = """---
id: comp-widget
title: Widget
status: draft
owners: [lselfors@gmail.com]
sealed: true
source_path: pipeline/widget/
realizes: [P-WIDGET]
---

# Widget

Purpose: fixture component for AC-SCENARIO-004.
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
Given a widget exists
When the widget is used
Then the widget behaves correctly
```
"""


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    component_dir = repo_root / "specs" / "components" / "widget"
    component_dir.mkdir(parents=True)
    (component_dir / "component.md").write_text(COMPONENT_MD)

    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True)
    (product_dir / "widget.md").write_text(CAPABILITY_MD)

    return repo_root


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _bundle_keys(bundle):
    if isinstance(bundle, dict):
        return set(bundle.keys())
    if dataclasses.is_dataclass(bundle):
        return {f.name for f in dataclasses.fields(bundle)}
    return set(vars(bundle).keys())


def _scenario_result(report, capability_id, scenario_id):
    capability = _get(report, capability_id)
    scenarios = _get(capability, "scenarios")
    for scenario in scenarios:
        if _get(scenario, "id") == scenario_id:
            return _get(scenario, "result")
    raise AssertionError(f"scenario {scenario_id} not found in report")


def _fake_outcome():
    return {
        "model_call_error": None,
        "file": {
            "path": "verification/capabilities/P-WIDGET/generated-test/test_cs_widget_001.py",
            "content": "def test_x():\n    assert True\n",
        },
    }


def test_generated_test_dispatched_fresh_on_every_call_no_cache_short_circuit(tmp_path):
    repo_root = _build_repo(tmp_path)
    log_path = tmp_path / "invocations.log"

    def fake_test_author(bundle):
        with open(log_path, "a") as f:
            f.write("invoked\n")
        return _fake_outcome()

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-widget"], repo_root, test_author=fake_test_author
    )
    capability_scenario_verifier.run_capability_scenarios(
        ["comp-widget"], repo_root, test_author=fake_test_author
    )

    invocations = log_path.read_text().splitlines()
    assert len(invocations) == 2


def test_bundle_keys_are_exactly_the_required_six(tmp_path):
    repo_root = _build_repo(tmp_path)
    bundle_keys_path = tmp_path / "bundle_keys.json"

    def fake_test_author(bundle):
        bundle_keys_path.write_text(json.dumps(sorted(_bundle_keys(bundle))))
        return _fake_outcome()

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-widget"], repo_root, test_author=fake_test_author
    )

    recorded_keys = set(json.loads(bundle_keys_path.read_text()))
    assert recorded_keys == {
        "capability_id",
        "scenario_id",
        "covers",
        "kind",
        "gherkin",
        "file",
    }


def test_missing_test_author_fails_generated_test_scenario(tmp_path):
    repo_root = _build_repo(tmp_path)

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-widget"], repo_root
    )

    result = _scenario_result(report, "P-WIDGET", "CS-WIDGET-001")
    assert result == "fail"