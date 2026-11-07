import json
from pathlib import Path

import pytest

import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


FAKE_TEST_AUTHOR_SOURCE = '''
import json
import os


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    if isinstance(bundle, dict):
        criterion_id = bundle.get("criterion_id")
    else:
        criterion_id = getattr(bundle, "criterion_id", None)

    log_path = os.path.join(repo_root, "test_author_calls.json")
    calls = []
    if os.path.exists(log_path):
        with open(log_path) as f:
            calls = json.load(f)
    calls.append({"criterion_id": criterion_id, "model": model, "seed": seed})
    with open(log_path, "w") as f:
        json.dump(calls, f)

    return {
        "component_id": "comp-cache-manager",
        "criterion_id": criterion_id,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
            "content": "def test_x():\\n    assert True\\n",
        },
        "model_call_error": None,
    }
'''


def _write_product_capability(repo_root: Path) -> None:
    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True, exist_ok=True)
    (product_dir / "widget.md").write_text(
        "---\n"
        "id: P-X\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is used\n"
        "Then it works\n"
        "```\n"
    )


def _write_realizing_component(repo_root: Path) -> None:
    component_dir = repo_root / "specs" / "components" / "cache-manager"
    component_dir.mkdir(parents=True, exist_ok=True)
    (component_dir / "component.md").write_text(
        "---\n"
        "id: comp-cache-manager\n"
        "title: Cache Manager\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-X]\n"
        "sealed: true\n"
        "source_path: pipeline/cache-manager/\n"
        "---\n"
        "\n"
        "Fixture sealed component realizing P-X.\n"
    )


def _write_fake_test_author(repo_root: Path) -> None:
    dep_dir = repo_root / "gen" / "test-author"
    dep_dir.mkdir(parents=True, exist_ok=True)
    (dep_dir / "test_author.py").write_text(FAKE_TEST_AUTHOR_SOURCE)


def _build_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_product_capability(repo_root)
    _write_realizing_component(repo_root)
    _write_fake_test_author(repo_root)
    return repo_root


def test_run_capability_gates_runs_scenario_writes_provenance_then_hits(tmp_path):
    repo_root = _build_repo(tmp_path)

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=2
    )

    assert _get(result, "hit") is False

    report = _get(result, "capability_scenario_report")
    capability_report = _get(report, "P-X")
    assert _get(capability_report, "overall") == "pass"
    scenarios = _get(capability_report, "scenarios")
    assert len(scenarios) == 1
    assert _get(scenarios[0], "id") == "CS-X-001"
    assert _get(scenarios[0], "result") == "pass"

    call_log_path = repo_root / "test_author_calls.json"
    assert call_log_path.exists()
    calls = json.loads(call_log_path.read_text())
    assert len(calls) == 1
    assert calls[0]["model"] == "m"
    assert calls[0]["seed"] == 2

    generated_test_path = (
        repo_root
        / "verification"
        / "capabilities"
        / "P-X"
        / "generated-test"
        / "test_cs_x_001.py"
    )
    assert generated_test_path.exists()
    assert "assert True" in generated_test_path.read_text()

    provenance_path = (
        repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    )
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
    assert record["realizing_components"] == ["comp-cache-manager"]
    assert record["capability_scenario_report"] == report
    assert record["model"] == "m"
    assert record["seed"] == 2

    check_result = capability_scenario_verifier.check_capability_provenance(
        "P-X", repo_root
    )
    assert _get(check_result, "hit") is True


def test_run_capability_gates_requires_model_when_no_record(tmp_path):
    repo_root = _build_repo(tmp_path)

    with pytest.raises(capability_scenario_verifier.ModelRequiredError):
        capability_scenario_verifier.run_capability_gates(
            "P-X", repo_root, model=None, seed=2
        )

    call_log_path = repo_root / "test_author_calls.json"
    assert not call_log_path.exists()

    provenance_path = (
        repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    )
    assert not provenance_path.exists()