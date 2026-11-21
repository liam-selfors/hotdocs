# hotdocs-criterion: sha256:313a3d9e623324815adece4c5b7cbdb9fb3ccb872138d55ae649b087c52bb980
import json
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _read_log(log_path):
    p = Path(log_path)
    if not p.exists():
        return []
    return [line for line in p.read_text().splitlines() if line.strip()]


def _build_fixture(repo_root, log_path):
    # python asset-kind adapter
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # a non-sealed component realizing P-X
    _write(
        repo_root / "specs" / "components" / "widget" / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "A small widget.\n",
    )
    _write(
        repo_root / "specs" / "components" / "widget" / "requirements" / "R-WIDGET-001.md",
        "**R-WIDGET-001** — MUST expose `value()` returning 1.\n",
    )
    _write(
        repo_root / "specs" / "components" / "widget" / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When value is called\n"
        "Then it returns 1\n"
        "```\n",
    )
    _write(
        repo_root / "gen" / "widget" / "widget.py",
        "def value():\n"
        "    return 1\n",
    )

    # the capability with exactly one scenario
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
        "Given a widget\n"
        "When value is called\n"
        "Then it returns 1\n"
        "```\n",
    )

    failing_content = "def test_x():\n    assert False\n"
    test_path = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"

    # fake test-author
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write('author_test ' + str(bundle['criterion_id']) + '\\n')\n"
        "    return {\n"
        "        'component_id': bundle.get('component_id') if isinstance(bundle, dict) else None,\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': " + repr(test_path) + ", 'content': " + repr(failing_content) + "},\n"
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
        "    return {'text': 'fail', 'model': model, 'backend': 'fake', 'model_call_error': None}\n",
    )


def test_recorded_failure_is_a_hit_and_not_rerun(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_fixture(repo_root, log_path)

    record_path = repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    assert not record_path.exists()

    # Fresh run: the only scenario fails.
    first = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, model="fake-model", seed=0, llm_backend=None
    )
    assert field(first, "hit") is False
    first_report = field(first, "capability_scenario_report")
    assert first_report is not None
    assert "P-X" in first_report
    entry = first_report["P-X"]
    assert field(entry, "overall") == "fail"
    scenarios = field(entry, "scenarios")
    assert len(scenarios) == 1
    assert field(scenarios[0], "id") == "CS-X-001"
    assert field(scenarios[0], "result") == "fail"

    assert record_path.is_file()
    record = json.loads(record_path.read_text())
    assert isinstance(record, dict)
    assert record["capability_scenario_report"] == json.loads(json.dumps(first_report))
    assert record["capability_scenario_report"]["P-X"]["overall"] == "fail"

    calls_after_first = _read_log(log_path)
    assert any(line.startswith("author_test") for line in calls_after_first)

    # Unchanged code: check, then gates with model None.
    checked = capability_scenario_verifier.check_capability_provenance("P-X", repo_root)
    assert field(checked, "hit") is True
    checked_report = field(checked, "capability_scenario_report")
    assert checked_report is not None
    assert field(checked_report["P-X"], "overall") == "fail"
    assert json.loads(json.dumps(checked_report)) == record["capability_scenario_report"]

    second = capability_scenario_verifier.run_capability_gates("P-X", repo_root, model=None)
    assert field(second, "hit") is True
    second_report = field(second, "capability_scenario_report")
    assert second_report is not None
    assert field(second_report["P-X"], "overall") == "fail"
    assert json.loads(json.dumps(second_report)) == record["capability_scenario_report"]

    # No fake module was called after the first run.
    assert _read_log(log_path) == calls_after_first
    # The record is unchanged.
    assert json.loads(record_path.read_text()) == record