from pathlib import Path

import pytest

import capability_scenario_verifier


def _get(obj, name):
    try:
        return obj[name]
    except (TypeError, KeyError):
        return getattr(obj, name)


def _find_scenario(scenarios, scenario_id):
    for scenario in scenarios:
        if _get(scenario, "id") == scenario_id:
            return scenario
    raise AssertionError(f"scenario {scenario_id} not found in {scenarios!r}")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_component(repo_root, slug, comp_id, realizes):
    content = (
        "---\n"
        f"id: {comp_id}\n"
        f"title: Fixture component {slug}\n"
        "status: draft\n"
        "owners: [fixture-owner]\n"
        f"realizes: [{', '.join(realizes)}]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "Synthetic fixture component for AC-SCENARIO-008.\n"
    )
    _write(repo_root / "specs" / "components" / slug / "component.md", content)


def _write_capability(repo_root, name, cap_id, scenarios):
    lines = [
        "---",
        f"id: {cap_id}",
        f"title: Fixture capability {cap_id}",
        "status: draft",
        "owners: [fixture-owner]",
        "---",
        "",
    ]
    for scenario_id, kind in scenarios:
        lines += [
            f"### {scenario_id}",
            "",
            f"Covers: {cap_id}",
            f"Kind: {kind}",
            "",
            "```gherkin",
            "Given a scenario fixture",
            "When run_capability_scenarios runs",
            "Then the scenario is decided by running its test",
            "```",
            "",
        ]
    _write(repo_root / "specs" / "product" / f"{name}.md", "\n".join(lines))


@pytest.fixture
def repo(tmp_path):
    _write_component(tmp_path, "one", "comp-one", ["P-ONE"])
    _write_component(tmp_path, "two", "comp-two", ["P-TWO"])
    _write_component(tmp_path, "three", "comp-three", ["P-THREE"])
    _write_component(tmp_path, "foo", "comp-foo", ["P-FOUR"])

    _write(tmp_path / "gen" / "one" / "one_mod.py", "def noop():\n    return None\n")
    _write(tmp_path / "gen" / "two" / "two_mod.py", "def noop():\n    return None\n")
    _write(tmp_path / "gen" / "three" / "three_mod.py", "def noop():\n    return None\n")
    _write(tmp_path / "gen" / "foo" / "foo_mod.py", "def value():\n    return 7\n")

    _write_capability(tmp_path, "one", "P-ONE", [("CS-ONE-001", "generated-test")])
    _write_capability(
        tmp_path,
        "two",
        "P-TWO",
        [
            ("CS-TWO-001", "generated-test"),
            ("CS-TWO-002", "generated-test"),
            ("CS-TWO-003", "generated-test"),
        ],
    )
    _write_capability(
        tmp_path,
        "three",
        "P-THREE",
        [("CS-THREE-001", "generated-test"), ("CS-THREE-002", "generated-test")],
    )
    _write_capability(tmp_path, "four", "P-FOUR", [("CS-FOUR-001", "generated-test")])

    return tmp_path


def test_failing_generated_test_fails_and_file_is_written(repo):
    def fake_test_author(bundle):
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-ONE/generated-test/test_cs_one_001.py",
                "content": "def test_x():\n    assert False\n",
            },
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-one"], repo, test_author=fake_test_author
    )

    cap = _get(report, "P-ONE")
    assert _get(cap, "overall") == "fail"
    scenario = _find_scenario(_get(cap, "scenarios"), "CS-ONE-001")
    assert _get(scenario, "result") == "fail"

    written = (
        repo
        / "verification"
        / "capabilities"
        / "P-ONE"
        / "generated-test"
        / "test_cs_one_001.py"
    )
    assert written.is_file()
    assert written.read_text() == "def test_x():\n    assert False\n"


def test_bad_returned_paths_fail_and_write_nothing(repo, tmp_path_factory):
    outside_dir = tmp_path_factory.mktemp("outside")
    bad_abs_path = str(outside_dir / "escape.py")

    paths = {
        "CS-TWO-001": "../escape.py",
        "CS-TWO-002": bad_abs_path,
        "CS-TWO-003": "notverification/x.py",
    }

    def fake_test_author(bundle):
        scenario_id = _get(bundle, "scenario_id")
        return {
            "model_call_error": None,
            "file": {
                "path": paths[scenario_id],
                "content": "def test_x():\n    assert True\n",
            },
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-two"], repo, test_author=fake_test_author
    )

    cap = _get(report, "P-TWO")
    scenarios = _get(cap, "scenarios")
    for scenario_id in paths:
        scenario = _find_scenario(scenarios, scenario_id)
        assert _get(scenario, "result") == "fail"

    assert not (repo.parent / "escape.py").exists()
    assert not Path(bad_abs_path).exists()
    assert not (repo / "notverification" / "x.py").exists()


def test_model_call_error_or_no_file_fails(repo):
    def fake_test_author(bundle):
        scenario_id = _get(bundle, "scenario_id")
        if scenario_id == "CS-THREE-001":
            return {
                "model_call_error": {"category": "network", "message": "boom"},
                "file": None,
            }
        return {"model_call_error": None, "file": None}

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-three"], repo, test_author=fake_test_author
    )

    cap = _get(report, "P-THREE")
    scenarios = _get(cap, "scenarios")
    for scenario_id in ("CS-THREE-001", "CS-THREE-002"):
        scenario = _find_scenario(scenarios, scenario_id)
        assert _get(scenario, "result") == "fail"


def test_realizing_component_code_dir_is_on_pythonpath_for_pass(repo):
    def fake_test_author(bundle):
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-FOUR/generated-test/test_cs_four_001.py",
                "content": (
                    "import foo_mod\n"
                    "\n"
                    "\n"
                    "def test_x():\n"
                    "    assert foo_mod.value() == 7\n"
                ),
            },
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo, test_author=fake_test_author
    )

    cap = _get(report, "P-FOUR")
    assert _get(cap, "overall") == "pass"
    scenario = _find_scenario(_get(cap, "scenarios"), "CS-FOUR-001")
    assert _get(scenario, "result") == "pass"