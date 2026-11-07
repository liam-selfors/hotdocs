import json
from pathlib import Path

import capability_scenario_verifier as cap_verifier


def _get(obj, key):
    try:
        return obj[key]
    except (TypeError, KeyError):
        return getattr(obj, key)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _call_count(call_log: Path) -> int:
    if not call_log.exists():
        return 0
    return len([ln for ln in call_log.read_text().splitlines() if ln.strip()])


def _setup_repo(repo_root: Path, call_log: Path) -> None:
    _write(
        repo_root / "specs" / "product" / "P-FOO.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        "---\n\n"
        "# Foo capability\n\n"
        "### CS-FOO-001\n\n"
        "Covers: P-FOO\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a foo\n"
        "When bar happens\n"
        "Then baz\n"
        "```\n",
    )

    author_test_src = (
        "import json\n\n"
        "CALL_LOG = %r\n\n"
        "def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):\n"
        "    try:\n"
        "        criterion_id = bundle[\"criterion_id\"]\n"
        "    except TypeError:\n"
        "        criterion_id = bundle.criterion_id\n"
        "    with open(CALL_LOG, \"a\") as f:\n"
        "        f.write(json.dumps({\"criterion_id\": criterion_id}) + \"\\n\")\n"
        "    return {\n"
        "        \"model_call_error\": None,\n"
        "        \"file\": {\n"
        "            \"path\": \"verification/capabilities/P-FOO/generated-test/test_cs_foo_001.py\",\n"
        "            \"content\": \"def test_x():\\n    assert False\\n\",\n"
        "        },\n"
        "    }\n"
    ) % (str(call_log),)
    _write(repo_root / "gen" / "test-author" / "test_author.py", author_test_src)

    llm_endpoint_src = (
        "def complete(prompt, model, backend=None, **params):\n"
        "    return {\"text\": \"ok\", \"model_call_error\": None}\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", llm_endpoint_src)


def test_failing_scenario_recorded_and_not_rerun(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    call_log = tmp_path / "author_test_calls.log"

    _setup_repo(repo_root, call_log)

    # Fresh run: the capability's only scenario fails.
    fresh_result = cap_verifier.run_capability_gates(
        "P-FOO", repo_root, model="claude-sonnet-5", seed=0, llm_backend=None
    )

    assert _get(fresh_result, "hit") is False
    fresh_report = _get(fresh_result, "capability_scenario_report")
    fresh_entry = _get(fresh_report, "P-FOO")
    assert _get(fresh_entry, "overall") == "fail"
    assert _call_count(call_log) == 1

    record_path = (
        repo_root / "verification" / "capabilities" / "P-FOO" / ".provenance.json"
    )
    assert record_path.exists()
    record = json.loads(record_path.read_text())
    assert record["capability_scenario_report"]["P-FOO"]["overall"] == "fail"
    assert record["gate_version"] == cap_verifier.GATE_VERSION

    # Same record, unchanged code: a pure read sees the recorded failure as a hit.
    check_result = cap_verifier.check_capability_provenance("P-FOO", repo_root)

    assert _get(check_result, "hit") is True
    check_report = _get(check_result, "capability_scenario_report")
    check_entry = _get(check_report, "P-FOO")
    assert _get(check_entry, "overall") == "fail"
    assert _call_count(call_log) == 1

    # run_capability_gates with model=None must not require a model on a hit,
    # must not re-run anything, and must return the same recorded failure.
    gate_result = cap_verifier.run_capability_gates("P-FOO", repo_root, model=None)

    assert _get(gate_result, "hit") is True
    gate_report = _get(gate_result, "capability_scenario_report")
    gate_entry = _get(gate_report, "P-FOO")
    assert _get(gate_entry, "overall") == "fail"
    assert _call_count(call_log) == 1