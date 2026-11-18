# hotdocs-criterion: sha256:d30070f48637604d57dc2d4c512dfc3197212cb007dfa594b11a3434a85c7f4d
import json
import shutil
from pathlib import Path

import pytest

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _live_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    gen = next((p for p in here.parents if p.name == "gen"), None)
    return gen.parent if gen is not None else None


def _copy_compiler(repo_root):
    live = _live_root()
    if live is None:
        return
    src = live / "pipeline" / "criterion-compiler"
    if src.is_dir():
        shutil.copytree(
            src,
            repo_root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )


def _fake_test_author_source(log_path):
    return (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'fn': 'author_test', 'criterion_id': bundle['criterion_id'], "
        "'criterion_text': bundle['criterion_text'], 'model': model, 'seed': seed}) + '\\n')\n"
        "    return {\n"
        "        'component_id': " + repr("comp-foo") + ",\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': " + repr("v1") + ",\n"
        "        'cache_hit': False,\n"
        "        'file': {\n"
        "            'path': " + repr("verification/capabilities/P-X/generated-test/test_cs_x_001.py") + ",\n"
        "            'content': " + repr("def test_x():\n    assert True\n") + ",\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )


def _fake_llm_endpoint_source(log_path):
    return (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'fn': 'complete', 'model': model}) + '\\n')\n"
        "    return {\n"
        "        'text': " + repr("PASS") + ",\n"
        "        'model': model,\n"
        "        'backend': " + repr("fake") + ",\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    # Realizing component (not sealed: concerns capability linkage).
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A component realizing P-X.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — MUST exist.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven nothing\nWhen nothing happens\nThen nothing changes\n```\n",
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "def foo():\n    return 1\n")

    # Capability with one generated-test scenario.
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [alice]\n"
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
        "Given a value is 1\n"
        "When the thing runs\n"
        "Then the result is 1\n"
        "```\n",
    )

    # Fake dependencies, flat-module shape.
    _write(repo_root / "gen" / "test-author" / "test_author.py", _fake_test_author_source(log_path))
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", _fake_llm_endpoint_source(log_path))

    _copy_compiler(repo_root)
    return repo_root, log_path


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _all_files(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def test_fresh_run_writes_record_then_check_hits(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    record_path = repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    assert not record_path.exists()

    result = capability_scenario_verifier.run_capability_gates("P-X", repo_root, "m", seed=2)

    # The scenario's test was authored via the fake and run.
    calls = [c for c in _read_log(log_path) if c["fn"] == "author_test"]
    assert len(calls) == 1
    assert calls[0]["criterion_id"] == "CS-X-001"
    assert calls[0]["model"] == "m"
    assert calls[0]["seed"] == 2

    assert field(result, "hit") is False
    report = field(result, "capability_scenario_report")
    assert list(report.keys()) == ["P-X"]
    entry = report["P-X"]
    assert field(entry, "overall") == "pass"
    scenarios = field(entry, "scenarios")
    assert len(scenarios) == 1
    assert field(scenarios[0], "id") == "CS-X-001"
    assert field(scenarios[0], "kind") == "generated-test"
    assert field(scenarios[0], "result") == "pass"

    # The committed record.
    assert record_path.is_file()
    record = json.loads(record_path.read_text(encoding="utf-8"))
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
    assert record["capability_scenario_report"] == json.loads(json.dumps(report))
    assert record["model"] == "m"
    assert record["seed"] == 2

    # Given that record now exists, a check is a hit.
    check = capability_scenario_verifier.check_capability_provenance("P-X", repo_root)
    assert field(check, "hit") is True
    assert json.loads(json.dumps(field(check, "capability_scenario_report"))) == record["capability_scenario_report"]


def test_miss_without_model_raises_and_touches_nothing(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    before = _all_files(repo_root)

    with pytest.raises(capability_scenario_verifier.ModelRequiredError):
        capability_scenario_verifier.run_capability_gates("P-X", repo_root, None)

    assert not log_path.exists()
    assert _read_log(log_path) == []
    assert not (repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json").exists()
    assert _all_files(repo_root) == before