import dataclasses
import json
import shutil
from pathlib import Path

import pytest

import capability_scenario_verifier


CAPABILITY_ID = "P-FOO"
SCENARIO_ID = "CS-FOO-001"
GENERATED_PATH = "verification/capabilities/P-FOO/generated-test/test_cs_foo_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def plain(value):
    """Recursively convert a returned value (dict or object) to plain data."""
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if hasattr(value, "__dict__") and not isinstance(value, (str, int, float, bool)):
        return {k: plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return value


def _tool_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"

    # Capability with exactly one scenario.
    _write(
        repo_root / "specs" / "product" / "foo.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n"
        "\n"
        "# Foo capability\n"
        "\n"
        "### CS-FOO-001\n"
        "\n"
        "Covers: P-FOO\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a foo is prepared\n"
        "When the foo runs\n"
        "Then the foo works\n"
        "```\n",
    )

    # One unsealed component realizing the capability.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: [P-FOO]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "def foo():\n    return 1\n")

    # Fake test-author: logs its invocation, returns a failing test.
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "import json\n"
        f"LOG = {json.dumps(str(log_path))}\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    cid = bundle['criterion_id'] if isinstance(bundle, dict) else getattr(bundle, 'criterion_id', None)\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'fn': 'author_test', 'criterion_id': cid}) + '\\n')\n"
        "    return {\n"
        "        'component_id': None,\n"
        "        'criterion_id': cid,\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {\n"
        f"            'path': {json.dumps(GENERATED_PATH)},\n"
        "            'content': 'def test_x():\\n    assert False\\n',\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "    }\n",
    )

    # Fake llm-endpoint: logs its invocation.
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "import json\n"
        f"LOG = {json.dumps(str(log_path))}\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'fn': 'complete'}) + '\\n')\n"
        "    return {\n"
        "        'text': 'FAIL',\n"
        "        'model': model,\n"
        "        'backend': 'fake',\n"
        "        'model_call_error': None,\n"
        "    }\n",
    )

    # Real criterion compiler copied from the live repository.
    tool_root = _tool_root()
    if tool_root is not None:
        src = tool_root / "pipeline" / "criterion-compiler"
        if src.is_dir():
            shutil.copytree(
                src,
                repo_root / "pipeline" / "criterion-compiler",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )

    return repo_root, log_path


def _log_lines(log_path: Path):
    if not log_path.exists():
        return []
    return [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_recorded_failure_is_a_hit_and_not_rerun(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    record_path = repo_root / "verification" / "capabilities" / CAPABILITY_ID / ".provenance.json"
    assert not record_path.exists()

    # --- Fresh run whose only scenario fails ---
    result = capability_scenario_verifier.run_capability_gates(
        CAPABILITY_ID, repo_root, model="fake-model", seed=0, llm_backend=None
    )
    assert field(result, "hit") is False
    report = field(result, "capability_scenario_report")
    assert report is not None
    entry = field(report, CAPABILITY_ID) if not isinstance(report, dict) else report[CAPABILITY_ID]
    assert field(entry, "overall") == "fail"
    scenarios = list(field(entry, "scenarios"))
    assert [field(s, "id") for s in scenarios] == [SCENARIO_ID]
    assert field(scenarios[0], "result") == "fail"

    # The fake test-author really produced the failing test.
    assert any(json.loads(l).get("fn") == "author_test" for l in _log_lines(log_path))

    # The record exists and carries that failing report.
    assert record_path.is_file()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert isinstance(record, dict)
    assert record["capability_id"] == CAPABILITY_ID
    assert plain(record["capability_scenario_report"]) == plain(report)
    assert record["capability_scenario_report"][CAPABILITY_ID]["overall"] == "fail"
    record_bytes = record_path.read_bytes()

    # --- Reset the invocation log; nothing below may call a fake ---
    if log_path.exists():
        log_path.unlink()

    checked = capability_scenario_verifier.check_capability_provenance(CAPABILITY_ID, repo_root)
    assert field(checked, "hit") is True
    checked_report = field(checked, "capability_scenario_report")
    assert checked_report is not None
    assert plain(checked_report)[CAPABILITY_ID]["overall"] == "fail"
    assert plain(checked_report) == plain(record["capability_scenario_report"])

    gated = capability_scenario_verifier.run_capability_gates(CAPABILITY_ID, repo_root, model=None)
    assert field(gated, "hit") is True
    gated_report = field(gated, "capability_scenario_report")
    assert gated_report is not None
    assert plain(gated_report)[CAPABILITY_ID]["overall"] == "fail"
    assert plain(gated_report) == plain(checked_report)

    # No fake module was called: the recorded failure was not re-run.
    assert _log_lines(log_path) == []
    # And the record was left untouched.
    assert record_path.read_bytes() == record_bytes