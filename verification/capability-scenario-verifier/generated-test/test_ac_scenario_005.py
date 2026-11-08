import json

import pytest

import capability_scenario_verifier


CAPABILITY_ID = "P-ZERO-EDIT"
SCENARIO_ID = "CS-ZERO-EDIT-001"


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write(
        repo_root / "specs" / "product" / "zero-edit.md",
        "---\n"
        "id: P-ZERO-EDIT\n"
        "title: Zero Edit capability\n"
        "status: ratified\n"
        "owners: [alice, bob]\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "---\n"
        "\n"
        "### " + SCENARIO_ID + "\n"
        "\n"
        "Covers: " + CAPABILITY_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it happens\n"
        "Then it works\n"
        "```\n",
    )

    log_path = tmp_path / "fake_calls.log"
    log_path_literal = repr(str(log_path))

    test_author_source = (
        "import json\n"
        "\n"
        "_LOG_PATH = " + log_path_literal + "\n"
        "\n"
        "def _bundle_get(bundle, key):\n"
        "    if isinstance(bundle, dict):\n"
        "        return bundle.get(key)\n"
        "    return getattr(bundle, key, None)\n"
        "\n"
        "def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):\n"
        "    with open(_LOG_PATH, 'a') as f:\n"
        "        f.write(json.dumps({'fn': 'author_test', "
        "'criterion_id': _bundle_get(bundle, 'criterion_id'), 'model': model}) + '\\n')\n"
        "    return {\n"
        "        'model_call_error': None,\n"
        "        'file': {\n"
        "            'path': 'verification/capabilities/P-ZERO-EDIT/generated-test/test_cs_zero_edit_001.py',\n"
        "            'content': 'def test_x():\\n    assert True\\n',\n"
        "        },\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", test_author_source)

    llm_endpoint_source = (
        "import json\n"
        "\n"
        "_LOG_PATH = " + log_path_literal + "\n"
        "\n"
        "def complete(prompt, model, backend=None, **params):\n"
        "    with open(_LOG_PATH, 'a') as f:\n"
        "        f.write(json.dumps({'fn': 'complete', 'model': model}) + '\\n')\n"
        "    return {'text': 'ok', 'model_call_error': None}\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", llm_endpoint_source)

    return repo_root, log_path


def _call_count(log_path):
    if not log_path.exists():
        return 0
    return len([line for line in log_path.read_text().splitlines() if line.strip()])


def _snapshot(repo_root):
    snap = {}
    for path in repo_root.rglob("*"):
        if path.is_file():
            snap[str(path.relative_to(repo_root))] = path.read_bytes()
    return snap


def _provenance_path(repo_root):
    return (
        repo_root
        / "verification"
        / "capabilities"
        / CAPABILITY_ID
        / ".provenance.json"
    )


def _bootstrap(repo_root):
    result = capability_scenario_verifier.run_capability_gates(
        CAPABILITY_ID, repo_root, "fake-model-v1"
    )
    assert _get(result, "hit") is False
    assert _provenance_path(repo_root).exists()
    return result


def test_hit_check_and_run_return_committed_report(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    _bootstrap(repo_root)
    assert _call_count(log_path) >= 1

    log_path.write_text("")

    check_result = capability_scenario_verifier.check_capability_provenance(
        CAPABILITY_ID, repo_root
    )
    assert _get(check_result, "hit") is True
    checked_report = _get(check_result, "capability_scenario_report")
    assert checked_report is not None
    assert CAPABILITY_ID in checked_report

    record = json.loads(_provenance_path(repo_root).read_text())
    assert checked_report == record["capability_scenario_report"]

    snapshot_before = _snapshot(repo_root)

    run_result_explicit_model = capability_scenario_verifier.run_capability_gates(
        CAPABILITY_ID, repo_root, "m"
    )
    assert _get(run_result_explicit_model, "hit") == _get(check_result, "hit")
    assert _get(run_result_explicit_model, "capability_scenario_report") == _get(
        check_result, "capability_scenario_report"
    )

    run_result_no_model = capability_scenario_verifier.run_capability_gates(
        CAPABILITY_ID, repo_root, None
    )
    assert _get(run_result_no_model, "hit") == _get(
        run_result_explicit_model, "hit"
    )
    assert _get(run_result_no_model, "capability_scenario_report") == _get(
        run_result_explicit_model, "capability_scenario_report"
    )

    assert _call_count(log_path) == 0

    snapshot_after = _snapshot(repo_root)
    assert snapshot_after == snapshot_before


@pytest.mark.parametrize("mutate", ["missing", "invalid_json", "wrong_gate_version"])
def test_miss_cases_yield_false_hit_and_null_report(tmp_path, mutate):
    repo_root, _log_path = _build_repo(tmp_path)
    _bootstrap(repo_root)

    provenance_path = _provenance_path(repo_root)

    if mutate == "missing":
        provenance_path.unlink()
    elif mutate == "invalid_json":
        provenance_path.write_text("{ this is not valid json ]")
    else:
        record = json.loads(provenance_path.read_text())
        record["gate_version"] = "capability_scenario_verifier@0.0.1-stale"
        provenance_path.write_text(json.dumps(record))

    result = capability_scenario_verifier.check_capability_provenance(
        CAPABILITY_ID, repo_root
    )
    assert _get(result, "hit") is False
    assert _get(result, "capability_scenario_report") is None


def test_unknown_capability_raises_from_both_functions(tmp_path):
    repo_root, _log_path = _build_repo(tmp_path)

    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.check_capability_provenance(
            "P-DOES-NOT-EXIST", repo_root
        )

    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.run_capability_gates(
            "P-DOES-NOT-EXIST", repo_root, "any-model"
        )