# hotdocs-criterion: sha256:26e807c2e5749c59a3686a059507aff37d3d5b84f715e6280625a2900fc92db4
import json
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root, log_path):
    # A non-sealed component realizing P-X, with its code under gen/foo/.
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
        "A tiny fixture component.\n",
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
        "# Library\n\n```\nfoo() -> int\n```\n",
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "def foo():\n    return 1\n")

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
        "Given a foo\n"
        "When foo is called\n"
        "Then it returns 1\n"
        "```\n",
    )

    # Fake test-author: logs each call, returns a test that fails.
    failing_content = "def test_x():\n    assert False\n"
    author_src = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):\n"
        "    cid = bundle[" + repr("criterion_id") + "]\n"
        "    with open(LOG_PATH, " + repr("a") + ") as fh:\n"
        "        fh.write(" + repr("author_test ") + " + str(cid) + " + repr("\n") + ")\n"
        "    name = " + repr("test_") + " + cid.lower().replace(" + repr("-") + ", " + repr("_") + ") + " + repr(".py") + "\n"
        "    return {\n"
        "        " + repr("component_id") + ": " + repr("P-X") + ",\n"
        "        " + repr("criterion_id") + ": cid,\n"
        "        " + repr("model") + ": model,\n"
        "        " + repr("seed") + ": seed,\n"
        "        " + repr("prompt_version") + ": " + repr("v1") + ",\n"
        "        " + repr("cache_hit") + ": False,\n"
        "        " + repr("model_call_error") + ": None,\n"
        "        " + repr("file") + ": {\n"
        "            " + repr("path") + ": " + repr("verification/capabilities/P-X/generated-test/") + " + name,\n"
        "            " + repr("content") + ": " + repr(failing_content) + ",\n"
        "        },\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", author_src)

    # Fake llm-endpoint: logs each call.
    endpoint_src = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def complete(prompt, model, backend=None, **params):\n"
        "    with open(LOG_PATH, " + repr("a") + ") as fh:\n"
        "        fh.write(" + repr("complete\n") + ")\n"
        "    return {\n"
        "        " + repr("text") + ": " + repr('{"result": "fail", "rationale": "fake"}') + ",\n"
        "        " + repr("model") + ": model,\n"
        "        " + repr("backend") + ": " + repr("fake") + ",\n"
        "        " + repr("model_call_error") + ": None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


def _log_lines(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_recorded_failure_is_a_hit_and_not_rerun(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_fixture(repo_root, log_path)

    record_path = repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    assert not record_path.exists()

    # Phase 1: fresh run whose only scenario fails.
    first = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, model="fake-model", seed=0
    )
    assert field(first, "hit") is False
    first_report = field(first, "capability_scenario_report")
    assert first_report is not None
    first_entry = first_report["P-X"] if isinstance(first_report, dict) else getattr(first_report, "P-X")
    assert field(first_entry, "overall") == "fail"

    phase1_calls = _log_lines(log_path)
    assert any(line.startswith("author_test") for line in phase1_calls), phase1_calls

    assert record_path.is_file()
    record_bytes = record_path.read_bytes()
    record = json.loads(record_bytes.decode("utf-8"))
    assert isinstance(record, dict)
    recorded_report = record["capability_scenario_report"]
    assert recorded_report["P-X"]["overall"] == "fail"
    if isinstance(first_report, dict):
        assert json.loads(json.dumps(first_report)) == recorded_report

    # Phase 2: unchanged code — check, then run with model None.
    checked = capability_scenario_verifier.check_capability_provenance("P-X", repo_root)
    assert field(checked, "hit") is True
    checked_report = field(checked, "capability_scenario_report")
    assert checked_report is not None
    checked_entry = checked_report["P-X"] if isinstance(checked_report, dict) else getattr(checked_report, "P-X")
    assert field(checked_entry, "overall") == "fail"

    second = capability_scenario_verifier.run_capability_gates("P-X", repo_root, model=None)
    assert field(second, "hit") is True
    second_report = field(second, "capability_scenario_report")
    assert second_report is not None
    second_entry = second_report["P-X"] if isinstance(second_report, dict) else getattr(second_report, "P-X")
    assert field(second_entry, "overall") == "fail"

    # No fake module was called during phase 2, and nothing was rewritten.
    assert _log_lines(log_path) == phase1_calls
    assert record_path.read_bytes() == record_bytes