import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _component_md(component_id, capability_id):
    return (
        "---\n"
        f"id: {component_id}\n"
        f"title: {component_id} Component\n"
        "status: draft\n"
        "owners: [spec-owner]\n"
        f"realizes: [{capability_id}]\n"
        "sealed: false\n"
        "---\n\n"
        f"# {component_id} Component\n"
    )


def _capability_md(capability_id):
    return (
        "---\n"
        f"id: {capability_id}\n"
        "title: Widget Capability\n"
        "status: draft\n"
        "owners: [spec-owner]\n"
        "---\n\n"
        "# Widget Capability\n\n"
        "### CS-WIDGET-001\n\n"
        f"Covers: {capability_id}\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is used\n"
        "Then it works\n"
        "```\n"
    )


def test_scenario_result_keyed_by_capability_not_component(tmp_path):
    repo_root = tmp_path

    _write(
        repo_root / "specs/components/alpha/component.md",
        _component_md("comp-alpha", "P-WIDGET"),
    )
    _write(repo_root / "gen/alpha/alpha.py", "def noop():\n    pass\n")

    _write(
        repo_root / "specs/components/beta/component.md",
        _component_md("comp-beta", "P-WIDGET"),
    )
    _write(repo_root / "gen/beta/beta.py", "def noop():\n    pass\n")

    _write(repo_root / "specs/product/widget.md", _capability_md("P-WIDGET"))

    calls = []

    def fake_test_author(bundle):
        calls.append(_get(bundle, "scenario_id"))
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-WIDGET/generated-test/test_cs_widget_001.py",
                "content": "def test_cs_widget_001():\n    assert True\n",
            },
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-alpha", "comp-beta"], repo_root, test_author=fake_test_author
    )

    assert isinstance(report, dict)
    assert set(report.keys()) == {"P-WIDGET"}

    widget = report["P-WIDGET"]
    assert _get(widget, "overall") == "pass"

    scenarios = _get(widget, "scenarios")
    assert len(scenarios) == 1

    scenario = scenarios[0]
    assert _get(scenario, "id") == "CS-WIDGET-001"
    assert _get(scenario, "kind") == "generated-test"
    assert _get(scenario, "result") == "pass"

    assert calls == ["CS-WIDGET-001"]

    written = (
        repo_root
        / "verification/capabilities/P-WIDGET/generated-test/test_cs_widget_001.py"
    )
    assert written.exists()
    assert "assert True" in written.read_text()