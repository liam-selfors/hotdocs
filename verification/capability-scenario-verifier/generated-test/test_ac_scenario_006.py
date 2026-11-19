# hotdocs-criterion: sha256:0e01858072a729b5a480a6262f3caca16c185cfbe12d821ff07c9aaad33d9933
import json
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


TEST_REL_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_repo(repo_root, call_log, run_log):
    repo_root = Path(repo_root)
    repo_root.mkdir(parents=True, exist_ok=True)

    # Planted python adapter.
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # One realizing component.
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
        "A fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — MUST expose `foo()` returning 1.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When foo is called\n"
        "Then it returns 1\n"
        "```\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo() -> int\n"
        "```\n",
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "def foo():\n    return 1\n")

    # One capability with one generated-test scenario.
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
        "Given a thing\n"
        "When it is used\n"
        "Then it works\n"
        "```\n",
    )

    # The generated test content: records that it ran.
    test_content = (
        "def test_x():\n"
        "    with open(" + repr(str(run_log)) + ", 'a') as f:\n"
        "        f.write('ran\\n')\n"
        "    assert True\n"
    )

    # Fake test-author.
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(call_log)) + "\n"
        "PATH = " + repr(TEST_REL_PATH) + "\n"
        "CONTENT = " + repr(test_content) + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps({'fn': 'author_test', 'criterion_id': bundle['criterion_id'],\n"
        "                            'model': model, 'seed': seed}) + '\\n')\n"
        "    if repo_root is not None:\n"
        "        target = Path(repo_root) / PATH\n"
        "        target.parent.mkdir(parents=True, exist_ok=True)\n"
        "        target.write_text(CONTENT)\n"
        "    return {\n"
        "        'component_id': 'comp-foo',\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': PATH, 'content': CONTENT},\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n",
    )

    # Fake llm-endpoint.
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "import json\n"
        "\n"
        "LOG = " + repr(str(call_log)) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps({'fn': 'complete', 'model': model}) + '\\n')\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'fake',\n"
        "            'model_call_error': None}\n",
    )
    return repo_root


def _read_log(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _snapshot(root):
    root = Path(root)
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_ac_scenario_006_fresh_run_records_then_hits(tmp_path):
    call_log = tmp_path / "calls.log"
    run_log = tmp_path / "ran.log"
    repo_root = _build_repo(tmp_path / "repo", call_log, run_log)

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=2
    )

    # The scenario's test was authored and actually run.
    calls = _read_log(call_log)
    author_calls = [c for c in calls if c["fn"] == "author_test"]
    assert author_calls, "fake author_test was never called"
    assert author_calls[0]["criterion_id"] == "CS-X-001"
    assert run_log.exists() and "ran" in run_log.read_text(), "scenario test was not run"

    assert field(result, "hit") is False
    report = field(result, "capability_scenario_report")
    assert report is not None
    entry = field(report, "P-X")
    assert field(entry, "overall") == "pass"
    scenarios = field(entry, "scenarios")
    assert len(scenarios) == 1
    assert field(scenarios[0], "id") == "CS-X-001"
    assert field(scenarios[0], "result") == "pass"

    record_path = repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
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
    assert record["capability_scenario_report"]["P-X"]["overall"] == "pass"
    assert record["model"] == "m"
    assert record["seed"] == 2

    # Given that record now exists: a check is a hit.
    check = capability_scenario_verifier.check_capability_provenance("P-X", repo_root)
    assert field(check, "hit") is True


def test_ac_scenario_006_model_none_on_miss_raises(tmp_path):
    call_log = tmp_path / "calls.log"
    run_log = tmp_path / "ran.log"
    repo_root = _build_repo(tmp_path / "repo", call_log, run_log)

    before = _snapshot(repo_root)

    with pytest.raises(capability_scenario_verifier.ModelRequiredError):
        capability_scenario_verifier.run_capability_gates("P-X", repo_root, None)

    assert _read_log(call_log) == [], "a fake module was called"
    assert not run_log.exists()
    after = _snapshot(repo_root)
    assert after == before, "a file was written"
    assert not (repo_root / "verification").exists()