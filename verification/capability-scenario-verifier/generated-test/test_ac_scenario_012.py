# hotdocs-criterion: sha256:b58fa09ca73365a52157e2464369595d5e67c921dd941d1d3eced42cf5c37875
import json
import sys
from pathlib import Path

import capability_scenario_verifier


CAP_ID = "P-X"
MODEL = "claude-sonnet-5"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"

    # Planted python adapter (test spec).
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # A component realizing the capability.
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
        "A fixture component.\n",
    )
    _write(
        repo_root / "gen" / "widget" / "widget.py",
        "def value():\n    return 1\n",
    )

    # The capability, with exactly one scenario.
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
        "When its value is read\n"
        "Then the value is 2\n"
        "```\n",
    )

    # Fake test-author: returns (and writes) a test that always fails.
    test_path = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"
    test_content = "def test_x():\n    assert False\n"
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "TEST_PATH = " + repr(test_path) + "\n"
        "TEST_CONTENT = " + repr(test_content) + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('author_test ' + str(bundle['criterion_id']) + '\\n')\n"
        "    if repo_root is not None:\n"
        "        target = Path(repo_root) / TEST_PATH\n"
        "        target.parent.mkdir(parents=True, exist_ok=True)\n"
        "        target.write_text(TEST_CONTENT)\n"
        "    return {\n"
        "        'component_id': 'comp-widget',\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': TEST_PATH, 'content': TEST_CONTENT},\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n",
    )

    # Fake llm-endpoint.
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('complete\\n')\n"
        "    return {'text': 'FAIL', 'model': model, 'backend': 'fake',\n"
        "            'model_call_error': None}\n",
    )

    return repo_root, log_path


def _overall(report):
    entry = field(report, CAP_ID)
    return field(entry, "overall")


def _log_lines(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text().splitlines() if line.strip()]


def test_recorded_failure_is_a_hit_and_not_rerun(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    record_path = repo_root / "verification" / "capabilities" / CAP_ID / ".provenance.json"

    # Fresh run whose only scenario fails.
    fresh = capability_scenario_verifier.run_capability_gates(
        CAP_ID, repo_root, model=MODEL, seed=0, llm_backend=None
    )
    assert field(fresh, "hit") is False
    fresh_report = field(fresh, "capability_scenario_report")
    assert fresh_report is not None
    assert _overall(fresh_report) == "fail"

    assert record_path.is_file(), "a failing run must still write the record"
    record = json.loads(record_path.read_text())
    assert isinstance(record, dict)
    recorded_report = record["capability_scenario_report"]
    assert recorded_report[CAP_ID]["overall"] == "fail"
    assert json.loads(json.dumps(fresh_report)) == recorded_report

    # The fresh run did call the fake test-author.
    assert _log_lines(log_path), "the fresh run should have called a fake module"

    # Reset the call log; the code is unchanged.
    log_path.write_text("")
    record_bytes = record_path.read_bytes()

    checked = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(checked, "hit") is True
    checked_report = field(checked, "capability_scenario_report")
    assert checked_report is not None
    assert _overall(checked_report) == "fail"

    gated = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, model=None)
    assert field(gated, "hit") is True
    gated_report = field(gated, "capability_scenario_report")
    assert gated_report is not None
    assert _overall(gated_report) == "fail"

    # Nothing re-run, nothing rewritten.
    assert _log_lines(log_path) == [], "no fake module may be called on a hit"
    assert record_path.read_bytes() == record_bytes