# hotdocs-criterion: sha256:669613b4f0a9fed21d07db0e42e77d9de17802b26ec91a848e33fa29e771b7b5
import json
import os
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


KIND_PYTHON_SRC = (
    "import sys\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
    "            \"interpreter\": sys.executable}\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_fixture(repo_root, author_log, complete_log, test_run_log):
    # planted python adapter
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", KIND_PYTHON_SRC)

    # one realizing component
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A component realizing P-X.\n",
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")

    # one capability with one generated-test scenario
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
        "Given a foo\n"
        "When it is used\n"
        "Then it works\n"
        "```\n",
    )

    # the generated test content: records that it ran, then passes
    test_content = (
        "def test_x():\n"
        "    with open(" + repr(str(test_run_log)) + ", 'a') as fh:\n"
        "        fh.write('ran\\n')\n"
        "    assert True\n"
    )
    test_path = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"

    author_src = (
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(author_log)) + "\n"
        "PATH = " + repr(test_path) + "\n"
        "CONTENT = " + repr(test_content) + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('author_test ' + str(bundle['criterion_id']) + '\\n')\n"
        "    if repo_root is not None:\n"
        "        target = Path(repo_root) / PATH\n"
        "        target.parent.mkdir(parents=True, exist_ok=True)\n"
        "        target.write_text(CONTENT)\n"
        "    return {\n"
        "        'component_id': None,\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': PATH, 'content': CONTENT},\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", author_src)

    complete_src = (
        "LOG = " + repr(str(complete_log)) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('complete\\n')\n"
        "    return {'text': 'PASS', 'model': model, 'backend': 'fake',\n"
        "            'model_call_error': None}\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", complete_src)


def _snapshot(root):
    snap = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            p = Path(dirpath) / name
            snap[str(p.relative_to(root))] = p.read_bytes()
    return snap


def _norm(value):
    return json.loads(json.dumps(value, default=lambda o: o.__dict__))


def test_ac_scenario_006(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()

    # --- Scenario 1: fresh run with model "m", seed 2 ---
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    author_log = logs / "author.log"
    complete_log = logs / "complete.log"
    test_run_log = logs / "testrun.log"
    _build_fixture(repo_root, author_log, complete_log, test_run_log)

    record_path = repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    assert not record_path.exists()

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=2
    )

    assert author_log.is_file(), "fake author_test was never called"
    assert test_run_log.is_file(), "the scenario's generated test was not run"
    assert "ran" in test_run_log.read_text()

    assert field(result, "hit") is False
    report = field(result, "capability_scenario_report")
    assert report is not None
    entry = field(report, "P-X")
    assert field(entry, "overall") == "pass"
    scenarios = field(entry, "scenarios")
    assert len(scenarios) == 1
    assert field(scenarios[0], "id") == "CS-X-001"
    assert field(scenarios[0], "kind") == "generated-test"
    assert field(scenarios[0], "result") == "pass"

    assert record_path.is_file()
    record = json.loads(record_path.read_text())
    assert isinstance(record, dict)
    assert set(record.keys()) == {
        "capability_id",
        "gate_version",
        "content_hash",
        "realizing_components",
        "capability_scenario_report",
        "model",
        "seed",
    }
    assert record["capability_id"] == "P-X"
    assert record["gate_version"] == capability_scenario_verifier.GATE_VERSION
    assert isinstance(record["content_hash"], str) and record["content_hash"]
    assert record["realizing_components"] == ["comp-foo"]
    assert record["model"] == "m"
    assert record["seed"] == 2
    assert record["capability_scenario_report"]["P-X"]["overall"] == "pass"
    assert record["capability_scenario_report"] == _norm(report)

    # --- Scenario 2: record exists, check is a hit ---
    check = capability_scenario_verifier.check_capability_provenance("P-X", repo_root)
    assert field(check, "hit") is True
    check_report = field(check, "capability_scenario_report")
    assert check_report is not None
    assert _norm(check_report) == record["capability_scenario_report"]

    # --- Scenario 3: no record and model None ---
    repo2 = tmp_path / "repo2"
    repo2.mkdir()
    author_log2 = logs / "author2.log"
    complete_log2 = logs / "complete2.log"
    test_run_log2 = logs / "testrun2.log"
    _build_fixture(repo2, author_log2, complete_log2, test_run_log2)

    before = _snapshot(repo2)
    logs_before = _snapshot(logs)

    with pytest.raises(capability_scenario_verifier.ModelRequiredError):
        capability_scenario_verifier.run_capability_gates("P-X", repo2, None)

    assert not author_log2.exists(), "fake author_test was called"
    assert not complete_log2.exists(), "fake complete was called"
    assert not test_run_log2.exists(), "a scenario test was run"
    assert not (repo2 / "verification" / "capabilities" / "P-X" / ".provenance.json").exists()
    assert _snapshot(repo2) == before
    assert _snapshot(logs) == logs_before