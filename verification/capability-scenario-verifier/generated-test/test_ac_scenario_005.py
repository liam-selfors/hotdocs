import json
from pathlib import Path

import pytest

import capability_scenario_verifier


def _dual_get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _snapshot(repo_root: Path):
    snap = {}
    for p in repo_root.rglob("*"):
        if p.is_file():
            snap[str(p.relative_to(repo_root))] = p.read_bytes()
    return snap


def _test_author_source(call_log_path: Path) -> str:
    return (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        f"_CALL_LOG = Path(r\"{call_log_path}\")\n"
        "\n"
        "def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):\n"
        "    cid = bundle[\"criterion_id\"] if isinstance(bundle, dict) else getattr(bundle, \"criterion_id\")\n"
        "    _CALL_LOG.parent.mkdir(parents=True, exist_ok=True)\n"
        "    with open(_CALL_LOG, \"a\") as f:\n"
        "        f.write(json.dumps({\"fn\": \"author_test\", \"criterion_id\": cid}) + \"\\n\")\n"
        "    suffix = cid.split(\"-\", 1)[1]\n"
        "    suffix = suffix.rsplit(\"-\", 1)[0]\n"
        "    cap_id = \"P-\" + suffix\n"
        "    fname = \"test_\" + cid.lower().replace(\"-\", \"_\") + \".py\"\n"
        "    path = \"verification/capabilities/\" + cap_id + \"/generated-test/\" + fname\n"
        "    return {\n"
        "        \"model_call_error\": None,\n"
        "        \"file\": {\"path\": path, \"content\": \"def test_x():\\n    assert True\\n\"},\n"
        "    }\n"
    )


def _llm_endpoint_source(call_log_path: Path) -> str:
    return (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        f"_CALL_LOG = Path(r\"{call_log_path}\")\n"
        "\n"
        "def complete(prompt, model, backend=None, **params):\n"
        "    _CALL_LOG.parent.mkdir(parents=True, exist_ok=True)\n"
        "    with open(_CALL_LOG, \"a\") as f:\n"
        "        f.write(json.dumps({\"fn\": \"complete\"}) + \"\\n\")\n"
        "    return {\"text\": \"ok\", \"model_call_error\": None}\n"
    )


def _write_capability_spec(repo_root: Path, cap_id: str, scenario_id: str) -> None:
    content = (
        "---\n"
        f"id: {cap_id}\n"
        f"title: {cap_id}\n"
        "status: ratified\n"
        "owners: [test-owner]\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "---\n"
        "\n"
        f"### {scenario_id}\n"
        "\n"
        f"Covers: {cap_id}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is used\n"
        "Then it behaves\n"
        "```\n"
    )
    path = repo_root / "specs" / "product" / f"{cap_id.lower()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def env(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    call_log = tmp_path / "fake_calls" / "calls.log"
    call_log.parent.mkdir(parents=True)
    call_log.write_text("")

    author_path = repo_root / "gen" / "test-author" / "test_author.py"
    author_path.parent.mkdir(parents=True, exist_ok=True)
    author_path.write_text(_test_author_source(call_log))

    endpoint_path = repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py"
    endpoint_path.parent.mkdir(parents=True, exist_ok=True)
    endpoint_path.write_text(_llm_endpoint_source(call_log))

    return repo_root, call_log


def test_hit_check_and_gates(env):
    repo_root, call_log = env
    _write_capability_spec(repo_root, "P-ZERO-EDIT", "CS-ZERO-EDIT-001")

    prime_result = capability_scenario_verifier.run_capability_gates(
        "P-ZERO-EDIT", repo_root, model="prime-model"
    )
    assert _dual_get(prime_result, "hit") is False
    assert "author_test" in call_log.read_text()

    record_path = repo_root / "verification" / "capabilities" / "P-ZERO-EDIT" / ".provenance.json"
    assert record_path.is_file()
    record = json.loads(record_path.read_text())
    assert record["capability_scenario_report"]["P-ZERO-EDIT"]["overall"] == "pass"

    call_log.write_text("")
    snapshot_before = _snapshot(repo_root)

    check_result = capability_scenario_verifier.check_capability_provenance(
        "P-ZERO-EDIT", repo_root
    )
    assert _dual_get(check_result, "hit") is True
    assert _dual_get(check_result, "capability_scenario_report") == record["capability_scenario_report"]
    assert call_log.read_text() == ""
    assert _snapshot(repo_root) == snapshot_before

    gates_result = capability_scenario_verifier.run_capability_gates(
        "P-ZERO-EDIT", repo_root, "m"
    )
    assert _dual_get(gates_result, "hit") == _dual_get(check_result, "hit")
    assert _dual_get(gates_result, "capability_scenario_report") == _dual_get(
        check_result, "capability_scenario_report"
    )
    assert call_log.read_text() == ""
    assert _snapshot(repo_root) == snapshot_before

    gates_result_none = capability_scenario_verifier.run_capability_gates(
        "P-ZERO-EDIT", repo_root, None
    )
    assert _dual_get(gates_result_none, "hit") == _dual_get(check_result, "hit")
    assert _dual_get(gates_result_none, "capability_scenario_report") == _dual_get(
        check_result, "capability_scenario_report"
    )
    assert call_log.read_text() == ""
    assert _snapshot(repo_root) == snapshot_before


def test_miss_no_record(env):
    repo_root, call_log = env
    _write_capability_spec(repo_root, "P-NO-RECORD", "CS-NO-RECORD-001")

    result = capability_scenario_verifier.check_capability_provenance("P-NO-RECORD", repo_root)
    assert _dual_get(result, "hit") is False
    assert _dual_get(result, "capability_scenario_report") is None


def test_miss_invalid_json_record(env):
    repo_root, call_log = env
    _write_capability_spec(repo_root, "P-BAD-JSON", "CS-BAD-JSON-001")

    record_dir = repo_root / "verification" / "capabilities" / "P-BAD-JSON"
    record_dir.mkdir(parents=True, exist_ok=True)
    (record_dir / ".provenance.json").write_text("{not valid json,,,")

    result = capability_scenario_verifier.check_capability_provenance("P-BAD-JSON", repo_root)
    assert _dual_get(result, "hit") is False
    assert _dual_get(result, "capability_scenario_report") is None


def test_miss_stale_gate_version(env):
    repo_root, call_log = env
    _write_capability_spec(repo_root, "P-STALE", "CS-STALE-001")

    capability_scenario_verifier.run_capability_gates("P-STALE", repo_root, model="prime-model")

    record_path = repo_root / "verification" / "capabilities" / "P-STALE" / ".provenance.json"
    record = json.loads(record_path.read_text())
    record["gate_version"] = str(record["gate_version"]) + "-stale"
    record_path.write_text(json.dumps(record))

    result = capability_scenario_verifier.check_capability_provenance("P-STALE", repo_root)
    assert _dual_get(result, "hit") is False
    assert _dual_get(result, "capability_scenario_report") is None


def test_unknown_capability_raises(env):
    repo_root, call_log = env

    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.check_capability_provenance("P-DOES-NOT-EXIST", repo_root)

    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.run_capability_gates(
            "P-DOES-NOT-EXIST", repo_root, model="m"
        )