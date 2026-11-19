# hotdocs-criterion: sha256:d30070f48637604d57dc2d4c512dfc3197212cb007dfa594b11a3434a85c7f4d
import json
from pathlib import Path

import pytest

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    author_log = tmp_path / "author_calls.log"
    complete_log = tmp_path / "complete_calls.log"
    marker = tmp_path / "scenario_test_ran.log"

    # One realizing component, not sealed, code under gen/foo/.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component realizing P-X.\n",
    )
    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "def value():\n    return 1\n",
    )

    # One capability with one generated-test scenario.
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Capability X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a foo component\n"
        "When its value is read\n"
        "Then the value is 1\n"
        "```\n",
    )

    # The scenario's test: passes, and leaves a marker proving it ran.
    test_content = (
        "def test_x():\n"
        "    with open(" + repr(str(marker)) + ", 'a') as f:\n"
        "        f.write('ran\\n')\n"
        "    assert True\n"
    )
    test_path = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"

    author_src = (
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(author_log)) + "\n"
        "CONTENT = " + repr(test_content) + "\n"
        "PATH = " + repr(test_path) + "\n"
        "GATE_VERSION = 'generated_test@1.2.0'\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(str(bundle['criterion_id']) + '\\n')\n"
        "    if repo_root is not None:\n"
        "        target = Path(repo_root) / PATH\n"
        "        target.parent.mkdir(parents=True, exist_ok=True)\n"
        "        target.write_text(CONTENT)\n"
        "    return {\n"
        "        'component_id': bundle.get('component_id') if isinstance(bundle, dict) else None,\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': PATH, 'content': CONTENT},\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", author_src)

    endpoint_src = (
        "LOG = " + repr(str(complete_log)) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write('call\\n')\n"
        "    return {\n"
        "        'text': 'pass',\n"
        "        'model': model,\n"
        "        'backend': 'fake',\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", endpoint_src)

    return repo_root, author_log, complete_log, marker


def _snapshot(root):
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_fresh_run_writes_record_then_check_hits(tmp_path):
    repo_root, author_log, complete_log, marker = _build_repo(tmp_path)

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=2
    )

    # The scenario's test was authored and run.
    assert author_log.is_file()
    assert "CS-X-001" in author_log.read_text()
    assert marker.is_file()
    assert "ran" in marker.read_text()

    assert field(result, "hit") is False
    report = field(result, "capability_scenario_report")
    assert report is not None
    entry = field(report, "P-X")
    assert field(entry, "overall") == "pass"
    scenarios = field(entry, "scenarios")
    assert len(scenarios) == 1
    assert field(scenarios[0], "id") == "CS-X-001"
    assert field(scenarios[0], "kind") == "generated-test"
    assert field(scenarios[0], "result") == "pass"

    record_path = (
        repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    )
    assert record_path.is_file()
    record = json.loads(record_path.read_text())
    assert isinstance(record, dict)
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
    assert record["realizing_components"] == ["comp-foo"]
    assert record["model"] == "m"
    assert record["seed"] == 2
    rec_report = record["capability_scenario_report"]
    assert set(rec_report.keys()) == {"P-X"}
    assert rec_report["P-X"]["overall"] == "pass"

    # Given that record now exists, a check is a hit.
    check = capability_scenario_verifier.check_capability_provenance(
        "P-X", repo_root
    )
    assert field(check, "hit") is True
    check_report = field(check, "capability_scenario_report")
    assert check_report is not None
    assert field(field(check_report, "P-X"), "overall") == "pass"


def test_miss_without_model_raises_and_touches_nothing(tmp_path):
    repo_root, author_log, complete_log, marker = _build_repo(tmp_path)
    before = _snapshot(repo_root)

    with pytest.raises(capability_scenario_verifier.ModelRequiredError):
        capability_scenario_verifier.run_capability_gates(
            "P-X", repo_root, None, seed=2
        )

    # No fake module was called.
    assert not author_log.exists()
    assert not complete_log.exists()
    assert not marker.exists()

    # No file was written.
    after = _snapshot(repo_root)
    assert after == before
    assert not (
        repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    ).exists()