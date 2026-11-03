import json
from pathlib import Path

import pytest

import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _make_generated_test_content(marker_path: Path) -> str:
    return (
        "import pathlib\n"
        "def test_x():\n"
        "    pathlib.Path(" + repr(str(marker_path)) + ").write_text(\"ran\")\n"
        "    assert True\n"
    )


def _build_fixture(repo_root: Path, log_path: Path, generated_test_content: str) -> None:
    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True, exist_ok=True)
    (product_dir / "p_x.md").write_text(
        "---\n"
        "id: P-X\n"
        "title: Capability P-X\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "---\n"
        "\n"
        "# P-X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When the widget is used\n"
        "Then the widget behaves correctly\n"
        "```\n"
    )

    component_dir = repo_root / "specs" / "components" / "widget"
    component_dir.mkdir(parents=True, exist_ok=True)
    (component_dir / "component.md").write_text(
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "Purpose: fixture realizing component for AC-SCENARIO-006.\n"
    )

    widget_gen_dir = repo_root / "gen" / "widget"
    widget_gen_dir.mkdir(parents=True, exist_ok=True)
    (widget_gen_dir / "widget.py").write_text("def noop():\n    pass\n")

    test_author_dir = repo_root / "gen" / "test-author"
    test_author_dir.mkdir(parents=True, exist_ok=True)
    module_lines = [
        "import json",
        "",
        "LOG_PATH = " + repr(str(log_path)),
        "RETURNED_CONTENT = " + repr(generated_test_content),
        "TEST_FILE_PATH = " + repr(
            "verification/capabilities/P-X/generated-test/test_cs_x_001.py"
        ),
        "",
        "def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):",
        "    if isinstance(bundle, dict):",
        "        criterion_id = bundle.get('criterion_id')",
        "        criterion_text = bundle.get('criterion_text')",
        "    else:",
        "        criterion_id = getattr(bundle, 'criterion_id', None)",
        "        criterion_text = getattr(bundle, 'criterion_text', None)",
        "    record = {",
        "        'model': model,",
        "        'seed': seed,",
        "        'criterion_id': criterion_id,",
        "        'criterion_text': criterion_text,",
        "    }",
        "    with open(LOG_PATH, 'a') as f:",
        "        f.write(json.dumps(record) + chr(10))",
        "    return {",
        "        'model_call_error': None,",
        "        'file': {'path': TEST_FILE_PATH, 'content': RETURNED_CONTENT},",
        "    }",
        "",
    ]
    (test_author_dir / "test_author.py").write_text("\n".join(module_lines))


def test_ac_scenario_006(tmp_path):
    repo_root = tmp_path / "repo1"
    log_path = tmp_path / "author_test_invocations.log"
    marker_path = tmp_path / "scenario_ran.marker"
    generated_test_content = _make_generated_test_content(marker_path)
    _build_fixture(repo_root, log_path, generated_test_content)

    provenance_path = (
        repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    )
    assert not provenance_path.exists()
    assert not marker_path.exists()

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=2
    )

    assert marker_path.exists()
    assert marker_path.read_text() == "ran"

    assert log_path.exists()
    log_lines = log_path.read_text().strip().splitlines()
    assert len(log_lines) >= 1
    invocation = json.loads(log_lines[0])
    assert invocation["model"] == "m"
    assert invocation["seed"] == 2
    assert invocation["criterion_id"] == "CS-X-001"

    assert _get(result, "hit") is False
    report = _get(result, "capability_scenario_report")
    px_report = _get(report, "P-X")
    assert _get(px_report, "overall") == "pass"

    assert provenance_path.exists()
    record = json.loads(provenance_path.read_text())
    assert set(record.keys()) == {
        "capability_id",
        "gate_version",
        "content_hash",
        "realizing_components",
        "capability_scenario_report",
        "model",
        "seed",
    }
    assert record["capability_id"] == "P-X"
    assert record["gate_version"] == capability_scenario_verifier.GATE_VERSION
    assert isinstance(record["content_hash"], str) and record["content_hash"]
    assert record["realizing_components"] == ["comp-widget"]
    assert record["model"] == "m"
    assert record["seed"] == 2
    px_record_report = record["capability_scenario_report"]["P-X"]
    assert px_record_report["overall"] == "pass"

    check_result = capability_scenario_verifier.check_capability_provenance(
        "P-X", repo_root
    )
    assert _get(check_result, "hit") is True

    repo_root2 = tmp_path / "repo2"
    log_path2 = tmp_path / "author_test_invocations2.log"
    marker_path2 = tmp_path / "scenario_ran2.marker"
    generated_test_content2 = _make_generated_test_content(marker_path2)
    _build_fixture(repo_root2, log_path2, generated_test_content2)

    provenance_path2 = (
        repo_root2 / "verification" / "capabilities" / "P-X" / ".provenance.json"
    )
    assert not provenance_path2.exists()

    with pytest.raises(capability_scenario_verifier.ModelRequiredError):
        capability_scenario_verifier.run_capability_gates("P-X", repo_root2, None)

    assert not log_path2.exists()
    assert not provenance_path2.exists()
    assert not marker_path2.exists()