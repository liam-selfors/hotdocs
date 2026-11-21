# hotdocs-criterion: sha256:69e92773192d76e0167f846ba750c3816e0c3a6ca7b3c1e0ac45894ff2efa8ba
import json
import os
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


CAP = "P-ZERO-EDIT"

KNOWN_REPORT = {
    "P-ZERO-EDIT": {
        "overall": "pass",
        "scenarios": [
            {"id": "CS-ZERO-EDIT-001", "kind": "generated-test", "result": "pass"}
        ],
    }
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def plain(result):
    return {
        "hit": field(result, "hit"),
        "capability_scenario_report": field(result, "capability_scenario_report"),
    }


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def record_path(repo_root):
    return repo_root / "verification" / "capabilities" / CAP / ".provenance.json"


def build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    log.write_text("")

    # python adapter
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # component realizing the capability
    write(
        repo_root / "specs" / "components" / "zero-edit" / "component.md",
        "---\n"
        "id: comp-zero-edit\n"
        "title: Zero Edit\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-ZERO-EDIT]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Zero Edit\n",
    )
    write(
        repo_root / "gen" / "zero-edit" / "zero_edit.py",
        "def f():\n    return 1\n",
    )

    # capability
    write(
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
        "Given an unchanged repository\n"
        "When verification runs\n"
        "Then nothing is regenerated\n"
        "```\n",
    )

    # fake test-author
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "LOG = " + repr(str(log)) + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('author_test\\n')\n"
        "    return {\n"
        "        'component_id': " + repr("comp-zero-edit") + ",\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {\n"
        "            'path': " + repr("verification/capabilities/P-ZERO-EDIT/generated-test/test_cs_zero_edit_001.py") + ",\n"
        "            'content': " + repr("def test_x():\n    assert True\n") + ",\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n",
    )

    # fake llm-endpoint
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "LOG = " + repr(str(log)) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('complete\\n')\n"
        "    return {'text': 'PASS', 'model': model, 'backend': 'fake',\n"
        "            'model_call_error': None}\n",
    )
    return repo_root, log


def prime(repo_root, log):
    """Produce a record with the current gate_version and content_hash,
    then pin its report to a known passing one."""
    capability_scenario_verifier.run_capability_gates(CAP, repo_root, "m")
    rp = record_path(repo_root)
    assert rp.is_file()
    record = json.loads(rp.read_text())
    assert record["gate_version"] == capability_scenario_verifier.GATE_VERSION
    record["capability_scenario_report"] = KNOWN_REPORT
    rp.write_text(json.dumps(record, indent=2))
    log.write_text("")
    return rp, record


def snapshot(repo_root):
    snap = {}
    for dirpath, dirnames, filenames in os.walk(repo_root):
        for name in filenames:
            p = Path(dirpath) / name
            st = p.stat()
            snap[str(p.relative_to(repo_root))] = (st.st_mtime_ns, st.st_size, p.read_bytes())
    return snap


@pytest.fixture(autouse=True)
def _no_bytecode(monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)


def test_hit_check_and_gates_reuse_record(tmp_path):
    repo_root, log = build_repo(tmp_path)
    prime(repo_root, log)

    check = capability_scenario_verifier.check_capability_provenance(CAP, repo_root)
    assert field(check, "hit") is True
    assert field(check, "capability_scenario_report") == KNOWN_REPORT

    before = snapshot(repo_root)
    log.write_text("")

    r1 = capability_scenario_verifier.run_capability_gates(CAP, repo_root, "m")
    r2 = capability_scenario_verifier.run_capability_gates(CAP, repo_root)
    r3 = capability_scenario_verifier.run_capability_gates(CAP, repo_root, None)

    for r in (r1, r2, r3):
        assert plain(r) == plain(check)

    assert log.read_text() == ""
    assert snapshot(repo_root) == before


def test_miss_cases(tmp_path):
    repo_root, log = build_repo(tmp_path)

    # no record
    res = capability_scenario_verifier.check_capability_provenance(CAP, repo_root)
    assert field(res, "hit") is False
    assert field(res, "capability_scenario_report") is None

    rp, record = prime(repo_root, log)

    # not valid JSON
    rp.write_text("{not json")
    res = capability_scenario_verifier.check_capability_provenance(CAP, repo_root)
    assert field(res, "hit") is False
    assert field(res, "capability_scenario_report") is None

    # different gate_version
    stale = dict(record)
    stale["gate_version"] = "capability_scenario_verifier@0.0.1"
    assert stale["gate_version"] != capability_scenario_verifier.GATE_VERSION
    rp.write_text(json.dumps(stale, indent=2))
    res = capability_scenario_verifier.check_capability_provenance(CAP, repo_root)
    assert field(res, "hit") is False
    assert field(res, "capability_scenario_report") is None


def test_unknown_capability_raises(tmp_path):
    repo_root, log = build_repo(tmp_path)
    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.check_capability_provenance("P-NOPE", repo_root)
    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.run_capability_gates("P-NOPE", repo_root, "m")