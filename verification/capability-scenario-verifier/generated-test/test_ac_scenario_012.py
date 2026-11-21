# hotdocs-criterion: sha256:608c6ae5a4206305c24c50150e42eca5a3ffbf834926cd9f36fbafe806395deb
import json
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_repo(repo_root, log_path):
    # Planted python adapter so nothing depends on the tool's own.
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # A realizing component.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "def hello():\n"
        "    return 1\n",
    )

    # The capability with exactly one scenario.
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [test-team]\n"
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
        "Given a thing\n"
        "When it runs\n"
        "Then it fails\n"
        "```\n",
    )

    # Fake test-author: writes a failing test and logs each call.
    failing_content = "def test_x():\n    assert False\n"
    test_rel_path = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "CONTENT = " + repr(failing_content) + "\n"
        "REL_PATH = " + repr(test_rel_path) + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('author_test ' + str(bundle['criterion_id']) + '\\n')\n"
        "    if repo_root is not None:\n"
        "        target = Path(repo_root) / REL_PATH\n"
        "        target.parent.mkdir(parents=True, exist_ok=True)\n"
        "        target.write_text(CONTENT)\n"
        "    return {\n"
        "        'component_id': 'comp-foo',\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': REL_PATH, 'content': CONTENT},\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n",
    )

    # Fake llm-endpoint: logs each call.
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('complete\\n')\n"
        "    return {'text': 'fail', 'model': model, 'backend': 'fake',\n"
        "            'model_call_error': None}\n",
    )


def _log_lines(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text().splitlines() if line.strip()]


def test_ac_scenario_012_recorded_failure_is_a_hit_and_not_rerun(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_repo(repo_root, log_path)

    # Fresh run whose only scenario fails.
    fresh = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, model="fake-model", seed=0, llm_backend=None
    )
    assert field(fresh, "hit") is False
    fresh_report = field(fresh, "capability_scenario_report")
    assert fresh_report is not None
    assert field(fresh_report["P-X"], "overall") == "fail"
    assert any(line.startswith("author_test") for line in _log_lines(log_path))

    record_path = repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    assert record_path.is_file()
    record_bytes = record_path.read_bytes()
    record = json.loads(record_bytes)
    assert isinstance(record, dict)
    recorded_report = record["capability_scenario_report"]
    assert recorded_report["P-X"]["overall"] == "fail"
    assert recorded_report == json.loads(json.dumps(fresh_report))

    # Unchanged code: clear the call log, then check and gate again with no model.
    if log_path.exists():
        log_path.unlink()

    checked = capability_scenario_verifier.check_capability_provenance("P-X", repo_root)
    assert field(checked, "hit") is True
    checked_report = field(checked, "capability_scenario_report")
    assert checked_report is not None
    assert field(checked_report["P-X"], "overall") == "fail"

    gated = capability_scenario_verifier.run_capability_gates("P-X", repo_root, model=None)
    assert field(gated, "hit") is True
    gated_report = field(gated, "capability_scenario_report")
    assert gated_report is not None
    assert field(gated_report["P-X"], "overall") == "fail"

    # No fake module was called, and nothing was rewritten.
    assert _log_lines(log_path) == []
    assert record_path.read_bytes() == record_bytes