from pathlib import Path

import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_fixture(repo_root: Path) -> None:
    component_dir = repo_root / "specs" / "components" / "foo"
    component_dir.mkdir(parents=True, exist_ok=True)
    (component_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo component\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: abc1234\n"
        "sealed: false\n"
        "realizes: [P-FOO]\n"
        "---\n\n"
        "# comp-foo\n\n"
        "A component that realizes P-FOO.\n",
        encoding="utf-8",
    )

    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "foo.py").write_text("", encoding="utf-8")

    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True, exist_ok=True)
    (product_dir / "foo.md").write_text(
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: abc1234\n"
        "---\n\n"
        "# P-FOO\n\n"
        "### CS-FOO-001\n\n"
        "Covers: P-FOO\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a widget\n"
        "When the widget is used\n"
        "Then the widget works\n"
        "```\n",
        encoding="utf-8",
    )


def _fake_test_author_outcome():
    return {
        "model_call_error": None,
        "file": {
            "path": "verification/capabilities/P-FOO/generated-test/test_cs_foo_001.py",
            "content": "def test_x():\n    assert True\n",
        },
    }


def test_generated_test_scenario_dispatched_on_both_calls_no_cache_short_circuit(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    calls = []

    def fake_test_author(bundle):
        calls.append(bundle)
        return _fake_test_author_outcome()

    report1 = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=fake_test_author,
    )
    report2 = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=fake_test_author,
    )

    assert len(calls) == 2

    for report in (report1, report2):
        capability = _get(report, "P-FOO")
        scenarios = _get(capability, "scenarios")
        assert len(scenarios) == 1
        assert _get(scenarios[0], "result") == "pass"


def test_bundle_passed_to_test_author_has_exact_keys(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    recorded_bundles = []

    def fake_test_author(bundle):
        recorded_bundles.append(bundle)
        return _fake_test_author_outcome()

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=fake_test_author,
    )

    assert len(recorded_bundles) == 1
    bundle = recorded_bundles[0]
    assert isinstance(bundle, dict)
    assert set(bundle.keys()) == {
        "capability_id",
        "scenario_id",
        "covers",
        "kind",
        "gherkin",
        "file",
    }


def test_missing_test_author_yields_fail_result(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root,
    )

    capability = _get(report, "P-FOO")
    scenarios = _get(capability, "scenarios")
    assert len(scenarios) == 1
    assert _get(scenarios[0], "result") == "fail"