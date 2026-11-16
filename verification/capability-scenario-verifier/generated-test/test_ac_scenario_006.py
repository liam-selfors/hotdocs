import json
import shutil
from pathlib import Path

import pytest

import capability_scenario_verifier


EXPECTED_RECORD_KEYS = {
    "capability_id",
    "gate_version",
    "content_hash",
    "realizing_components",
    "capability_scenario_report",
    "model",
    "seed",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _fake_test_author_source(author_log, marker):
    return (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        f"_LOG = {str(author_log)!r}\n"
        f"_MARKER = {str(marker)!r}\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    criterion_id = bundle['criterion_id']\n"
        "    _text = bundle['criterion_text']\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'criterion_id': criterion_id, 'model': model,\n"
        "                             'seed': seed}) + '\\n')\n"
        "    name = 'test_' + criterion_id.lower().replace('-', '_') + '.py'\n"
        "    rel = 'verification/capabilities/P-X/generated-test/' + name\n"
        "    content = (\n"
        "        'from pathlib import Path\\n'\n"
        "        '\\n'\n"
        "        '\\n'\n"
        "        'def test_x():\\n'\n"
        "        '    Path(' + repr(_MARKER) + ').write_text(\"ran\")\\n'\n"
        "        '    assert True\\n'\n"
        "    )\n"
        "    if repo_root is not None:\n"
        "        target = Path(repo_root) / rel\n"
        "        target.parent.mkdir(parents=True, exist_ok=True)\n"
        "        target.write_text(content)\n"
        "    return {\n"
        "        'component_id': None,\n"
        "        'criterion_id': criterion_id,\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': rel, 'content': content},\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )


def _fake_llm_endpoint_source(llm_log):
    return (
        "import json\n"
        "\n"
        f"_LOG = {str(llm_log)!r}\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'model': model}) + '\\n')\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'fake',\n"
        "            'model_call_error': None}\n"
    )


def _build_repo(repo_root, author_log, llm_log, marker):
    repo_root.mkdir(parents=True, exist_ok=True)

    # A realizing component.
    _write(
        repo_root / "specs/components/widget/component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "A small widget component.\n",
    )
    _write(
        repo_root / "specs/components/widget/requirements/R-WIDGET-001.md",
        "**R-WIDGET-001** — MUST expose `use()` returning `True`.\n",
    )
    _write(
        repo_root / "specs/components/widget/acceptance/AC-WIDGET-001.md",
        "# AC-WIDGET-001\n\nCovers: R-WIDGET-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a widget\nWhen use() is called\nThen it returns true\n```\n",
    )
    _write(
        repo_root / "specs/components/widget/interface/library.md",
        "# Library\n\n```\nuse() -> bool\n```\n",
    )
    _write(repo_root / "specs/components/widget/constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "gen/widget/widget.py", "def use():\n    return True\n")

    # A capability with one generated-test scenario.
    _write(
        repo_root / "specs/product/x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [tester]\n"
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
        "Given a widget\n"
        "When it is used\n"
        "Then it works\n"
        "```\n",
    )

    # Fake dependencies.
    _write(
        repo_root / "gen/test-author/test_author.py",
        _fake_test_author_source(author_log, marker),
    )
    _write(repo_root / "gen/llm-endpoint/llm_endpoint.py", _fake_llm_endpoint_source(llm_log))

    # Real compiler, copied from the live repository.
    tool_root = _tool_root()
    if tool_root is not None:
        src = tool_root / "pipeline" / "criterion-compiler"
        if src.is_dir():
            shutil.copytree(
                src,
                repo_root / "pipeline" / "criterion-compiler",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )


def _snapshot(root):
    snap = {}
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_file():
            snap[rel] = p.read_bytes()
        else:
            snap[rel] = None
    return snap


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_ac_scenario_006_fresh_run_records_then_hits(tmp_path):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir()
    author_log = logs / "author.jsonl"
    llm_log = logs / "llm.jsonl"
    marker = logs / "scenario_test_ran.txt"
    _build_repo(repo_root, author_log, llm_log, marker)

    record_path = repo_root / "verification/capabilities/P-X/.provenance.json"
    assert not record_path.exists()

    result = capability_scenario_verifier.run_capability_gates("P-X", repo_root, "m", seed=2)

    # The scenario's test was authored and run.
    calls = _read_log(author_log)
    assert any(c["criterion_id"] == "CS-X-001" for c in calls), calls
    assert marker.exists(), "the scenario's generated test was not run"

    assert field(result, "hit") is False
    report = field(result, "capability_scenario_report")
    assert report is not None
    assert list(report.keys() if isinstance(report, dict) else vars(report).keys()) == ["P-X"]
    entry = field(report, "P-X")
    assert field(entry, "overall") == "pass"
    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 1
    assert field(scenarios[0], "id") == "CS-X-001"
    assert field(scenarios[0], "kind") == "generated-test"
    assert field(scenarios[0], "result") == "pass"

    # The committed record exists with exactly the documented keys.
    assert record_path.is_file()
    record = json.loads(record_path.read_text())
    assert isinstance(record, dict)
    assert set(record.keys()) == EXPECTED_RECORD_KEYS
    assert record["capability_id"] == "P-X"
    assert record["gate_version"] == capability_scenario_verifier.GATE_VERSION
    assert isinstance(record["content_hash"], str) and record["content_hash"]
    assert record["realizing_components"] == ["comp-widget"]
    assert record["model"] == "m"
    assert record["seed"] == 2
    rec_report = record["capability_scenario_report"]
    assert set(rec_report.keys()) == {"P-X"}
    assert rec_report["P-X"]["overall"] == "pass"

    # Given that record now exists, the check is a hit.
    check = capability_scenario_verifier.check_capability_provenance("P-X", repo_root)
    assert field(check, "hit") is True
    check_report = field(check, "capability_scenario_report")
    assert check_report is not None
    assert field(field(check_report, "P-X"), "overall") == "pass"


def test_ac_scenario_006_model_none_on_miss_raises(tmp_path):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir()
    author_log = logs / "author.jsonl"
    llm_log = logs / "llm.jsonl"
    marker = logs / "scenario_test_ran.txt"
    _build_repo(repo_root, author_log, llm_log, marker)

    before = _snapshot(repo_root)

    with pytest.raises(capability_scenario_verifier.ModelRequiredError):
        capability_scenario_verifier.run_capability_gates("P-X", repo_root, None)

    # No fake module was called.
    assert not author_log.exists()
    assert not llm_log.exists()
    assert not marker.exists()

    # No file was written.
    after = _snapshot(repo_root)
    assert after == before
    assert not (repo_root / "verification/capabilities/P-X/.provenance.json").exists()