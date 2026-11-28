# hotdocs-criterion: sha256:dcea9f10a56db05c614e77a28131e6988d8bdf3e50b5a38e7219143d17c74023
import json
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


CAP_ID = "P-ZERO-EDIT"
SCENARIO_ID = "CS-ZERO-EDIT-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_repo(repo_root, log_path):
    # planted python adapter
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # a component realizing the capability
    write(
        repo_root / "specs" / "components" / "zero" / "component.md",
        "---\n"
        "id: comp-zero\n"
        "title: Zero\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-ZERO-EDIT]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Zero\n",
    )
    write(repo_root / "gen" / "zero" / "zero.py", "VALUE = 1\n")

    # the capability
    write(
        repo_root / "specs" / "product" / "zero-edit.md",
        "---\n"
        "id: P-ZERO-EDIT\n"
        "title: Zero Edit\n"
        "status: draft\n"
        "owners: [test-team]\n"
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
        "Given an unchanged spec\n"
        "When verification runs\n"
        "Then nothing is regenerated\n"
        "```\n",
    )

    test_path = "verification/capabilities/P-ZERO-EDIT/generated-test/test_cs_zero_edit_001.py"
    test_content = "def test_x():\n    assert True\n"

    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('author_test\\n')\n"
        "    return {\n"
        "        'component_id': 'comp-zero',\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': " + repr(test_path) + ", 'content': " + repr(test_content) + "},\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n",
    )

    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('complete\\n')\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'fake',\n"
        "            'model_call_error': None}\n",
    )


def snapshot(root):
    snap = {}
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        st = p.stat()
        if p.is_dir():
            snap[rel] = ("dir", None, st.st_mtime_ns)
        else:
            snap[rel] = ("file", p.read_bytes(), st.st_mtime_ns)
    return snap


def log_lines(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text().splitlines() if line.strip()]


def test_ac_scenario_005(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    build_repo(repo_root, log_path)

    record_path = repo_root / "verification" / "capabilities" / CAP_ID / ".provenance.json"

    # Produce a record carrying the current gate_version and content_hash.
    fresh = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, "m")
    assert field(fresh, "hit") is False
    assert record_path.is_file()

    record = json.loads(record_path.read_text())
    assert record["gate_version"] == capability_scenario_verifier.GATE_VERSION

    # Make the committed report a known passing one; the key is unchanged.
    passing_report = {
        CAP_ID: {
            "overall": "pass",
            "scenarios": [{"id": SCENARIO_ID, "kind": "generated-test", "result": "pass"}],
        }
    }
    record["capability_scenario_report"] = passing_report
    record_path.write_text(json.dumps(record, indent=2))
    good_record_bytes = record_path.read_bytes()

    # Reset the fake call log.
    if log_path.exists():
        log_path.unlink()

    # --- check hit ---
    check = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(check, "hit") is True
    assert field(check, "capability_scenario_report") == passing_report

    # --- run_capability_gates on a hit ---
    before = snapshot(repo_root)
    result = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, "m")
    assert field(result, "hit") == field(check, "hit")
    assert field(result, "capability_scenario_report") == field(check, "capability_scenario_report")

    result_none = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, None)
    assert field(result_none, "hit") == field(check, "hit")
    assert field(result_none, "capability_scenario_report") == field(check, "capability_scenario_report")

    after = snapshot(repo_root)
    assert after == before
    assert log_lines(log_path) == []

    # --- misses ---
    # no record
    record_path.unlink()
    miss = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(miss, "hit") is False
    assert field(miss, "capability_scenario_report") is None

    # not valid JSON
    record_path.write_text("{ this is not json")
    miss = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(miss, "hit") is False
    assert field(miss, "capability_scenario_report") is None

    # different gate_version
    stale = json.loads(good_record_bytes.decode())
    stale["gate_version"] = "capability_scenario_verifier@0.0.1"
    record_path.write_text(json.dumps(stale, indent=2))
    miss = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(miss, "hit") is False
    assert field(miss, "capability_scenario_report") is None

    record_path.write_bytes(good_record_bytes)

    # --- unknown capability ---
    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.check_capability_provenance("P-NOPE", repo_root)
    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.run_capability_gates("P-NOPE", repo_root, "m")

    assert log_lines(log_path) == []