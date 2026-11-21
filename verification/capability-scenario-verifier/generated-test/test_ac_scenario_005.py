# hotdocs-criterion: sha256:02fa257b70f64d2d74e2aa24b8c5870133f5ec9f6a3228b4edddcf159faedf08
import json
import os
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


CAP_ID = "P-ZERO-EDIT"
RECORD_REL = Path("verification") / "capabilities" / CAP_ID / ".provenance.json"
PASSING_REPORT = {
    CAP_ID: {
        "overall": "pass",
        "scenarios": [
            {"id": "CS-ZERO-EDIT-001", "kind": "generated-test", "result": "pass"}
        ],
    }
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_repo(repo_root, log_path):
    # python asset-kind adapter
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {'ok': True, 'reason': '', 'versions': {}, 'lockfile_sha256': None,\n"
        "            'interpreter': sys.executable}\n",
    )

    # realizing component
    _write(
        repo_root / "specs" / "components" / "zero-edit-impl" / "component.md",
        "---\n"
        "id: comp-zero-edit-impl\n"
        "title: Zero Edit Impl\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-ZERO-EDIT]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Zero Edit Impl\n",
    )
    _write(
        repo_root / "gen" / "zero-edit-impl" / "zero_edit_impl.py",
        "def value():\n    return 1\n",
    )

    # capability
    _write(
        repo_root / "specs" / "product" / "zero-edit.md",
        "---\n"
        "id: P-ZERO-EDIT\n"
        "title: Zero Edit\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Zero Edit\n"
        "\n"
        "### CS-ZERO-EDIT-001\n"
        "\n"
        "Covers: P-ZERO-EDIT\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a repository with no edits\n"
        "When verification runs\n"
        "Then nothing is regenerated\n"
        "```\n",
    )

    # fake test-author
    author_content = "def test_x():\n    assert True\n"
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write('author_test\\n')\n"
        "    criterion_id = bundle['criterion_id'] if isinstance(bundle, dict) else getattr(bundle, 'criterion_id')\n"
        "    return {\n"
        "        'component_id': '',\n"
        "        'criterion_id': criterion_id,\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {\n"
        "            'path': " + repr("verification/capabilities/P-ZERO-EDIT/generated-test/test_cs_zero_edit_001.py") + ",\n"
        "            'content': " + repr(author_content) + ",\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n",
    )

    # fake llm-endpoint
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write('complete\\n')\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'fake',\n"
        "            'model_call_error': None}\n",
    )


def _snapshot(repo_root):
    snap = {}
    for dirpath, dirnames, filenames in os.walk(repo_root):
        snap[("dir", os.path.relpath(dirpath, repo_root))] = None
        for name in filenames:
            p = os.path.join(dirpath, name)
            st = os.stat(p)
            with open(p, "rb") as f:
                data = f.read()
            snap[("file", os.path.relpath(p, repo_root))] = (data, st.st_mtime_ns, st.st_size)
    return snap


def _read_log(log_path):
    if not log_path.exists():
        return ""
    return log_path.read_text()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logdir = tmp_path / "logs"
    logdir.mkdir()
    log_path = logdir / "calls.log"
    _build_repo(repo_root, log_path)
    return repo_root, log_path


def _bootstrap(repo_root, log_path):
    """Produce a committed record carrying the current gate_version and
    content_hash, then make its report a known passing one."""
    capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, "m")
    record_path = repo_root / RECORD_REL
    assert record_path.is_file()
    record = json.loads(record_path.read_text())
    assert record["gate_version"] == capability_scenario_verifier.GATE_VERSION
    record["capability_scenario_report"] = PASSING_REPORT
    record_path.write_text(json.dumps(record, indent=2))
    if log_path.exists():
        log_path.unlink()
    return record_path, record


def test_hit_returns_record_report(env):
    repo_root, log_path = env
    _bootstrap(repo_root, log_path)

    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is True
    assert field(result, "capability_scenario_report") == PASSING_REPORT


def test_run_gates_on_hit_does_nothing(env):
    repo_root, log_path = env
    _bootstrap(repo_root, log_path)

    check = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(check, "hit") is True

    before = _snapshot(repo_root)
    if log_path.exists():
        log_path.unlink()

    result = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, "m")
    assert field(result, "hit") == field(check, "hit")
    assert field(result, "capability_scenario_report") == field(check, "capability_scenario_report")
    assert _read_log(log_path) == ""
    assert _snapshot(repo_root) == before

    result_none = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, None)
    assert field(result_none, "hit") == field(check, "hit")
    assert field(result_none, "capability_scenario_report") == field(check, "capability_scenario_report")
    assert _read_log(log_path) == ""
    assert _snapshot(repo_root) == before

    result_default = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root)
    assert field(result_default, "hit") == field(check, "hit")
    assert field(result_default, "capability_scenario_report") == field(check, "capability_scenario_report")
    assert _read_log(log_path) == ""
    assert _snapshot(repo_root) == before


def test_no_record_is_miss(env):
    repo_root, log_path = env
    assert not (repo_root / RECORD_REL).exists()
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is False
    assert field(result, "capability_scenario_report") is None


def test_invalid_json_record_is_miss(env):
    repo_root, log_path = env
    record_path, _ = _bootstrap(repo_root, log_path)
    record_path.write_text("{this is not json")
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is False
    assert field(result, "capability_scenario_report") is None


def test_different_gate_version_is_miss(env):
    repo_root, log_path = env
    record_path, record = _bootstrap(repo_root, log_path)
    record["gate_version"] = "capability_scenario_verifier@0.0.1"
    assert record["gate_version"] != capability_scenario_verifier.GATE_VERSION
    record_path.write_text(json.dumps(record, indent=2))
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is False
    assert field(result, "capability_scenario_report") is None


def test_unknown_capability_raises(env):
    repo_root, log_path = env
    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.check_capability_provenance("P-NO-SUCH-CAP", repo_root)
    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.run_capability_gates("P-NO-SUCH-CAP", repo_root, "m")