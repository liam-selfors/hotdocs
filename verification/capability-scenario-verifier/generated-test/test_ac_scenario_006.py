# hotdocs-criterion: sha256:a3ea909f2be7f04f938154851f23cfbaeeeda647f4e14211be59b065ed31de55
import json
import os
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def entry(report, key):
    if isinstance(report, dict):
        return report[key]
    return getattr(report, key)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def snapshot(root):
    files = {}
    for p in Path(root).rglob("*"):
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        if p.is_file():
            files[str(p.relative_to(root))] = p.read_bytes()
    return files


def build_fixture(repo_root, author_log, endpoint_log, run_log):
    repo_root = Path(repo_root)

    # Planted python adapter.
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # One realizing component.
    write(
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
    write(
        repo_root / "gen" / "foo" / "foo.py",
        "def value():\n"
        "    return 1\n",
    )

    # One capability with one generated-test scenario.
    write(
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
        "Given a foo component\n"
        "When its value is read\n"
        "Then the value is 1\n"
        "```\n",
    )

    test_content = (
        "def test_x():\n"
        "    with open(" + repr(str(run_log)) + ", \"a\") as f:\n"
        "        f.write(\"ran\\n\")\n"
        "    assert True\n"
    )

    # Fake test-author.
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(author_log)) + "\n"
        "PATH = " + repr("verification/capabilities/P-X/generated-test/test_cs_x_001.py") + "\n"
        "CONTENT = " + repr(test_content) + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, \"a\") as f:\n"
        "        f.write(\"author_test \" + str(model) + \" \" + str(seed) + \"\\n\")\n"
        "    if repo_root is not None:\n"
        "        target = Path(repo_root) / PATH\n"
        "        target.parent.mkdir(parents=True, exist_ok=True)\n"
        "        target.write_text(CONTENT)\n"
        "    criterion_id = bundle.get(\"criterion_id\") if isinstance(bundle, dict) else None\n"
        "    return {\n"
        "        \"component_id\": \"comp-foo\",\n"
        "        \"criterion_id\": criterion_id,\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"prompt_version\": \"v1\",\n"
        "        \"cache_hit\": False,\n"
        "        \"file\": {\"path\": PATH, \"content\": CONTENT},\n"
        "        \"model_call_error\": None,\n"
        "        \"repair_attempts\": 0,\n"
        "        \"probe_findings\": [],\n"
        "    }\n",
    )

    # Fake llm-endpoint.
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "LOG = " + repr(str(endpoint_log)) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, \"a\") as f:\n"
        "        f.write(\"complete \" + str(model) + \"\\n\")\n"
        "    return {\"text\": \"pass\", \"model\": model, \"backend\": \"fake\",\n"
        "            \"model_call_error\": None}\n",
    )


def test_fresh_run_records_and_then_hits(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    author_log = logs / "author.log"
    endpoint_log = logs / "endpoint.log"
    run_log = logs / "run.log"
    build_fixture(repo_root, author_log, endpoint_log, run_log)

    record_path = repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    assert not record_path.exists()

    result = capability_scenario_verifier.run_capability_gates("P-X", repo_root, "m", seed=2)

    # The scenario's test was authored and run.
    assert author_log.is_file()
    assert author_log.read_text().strip() != ""
    assert run_log.is_file()
    assert "ran" in run_log.read_text()

    assert field(result, "hit") is False
    report = field(result, "capability_scenario_report")
    px = entry(report, "P-X")
    assert field(px, "overall") == "pass"
    scenarios = field(px, "scenarios")
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

    # Given that record now exists, a check is a hit.
    check = capability_scenario_verifier.check_capability_provenance("P-X", repo_root)
    assert field(check, "hit") is True
    check_report = field(check, "capability_scenario_report")
    assert field(entry(check_report, "P-X"), "overall") == "pass"


def test_miss_with_no_model_raises_before_anything(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    author_log = logs / "author.log"
    endpoint_log = logs / "endpoint.log"
    run_log = logs / "run.log"
    build_fixture(repo_root, author_log, endpoint_log, run_log)

    before = snapshot(repo_root)

    with pytest.raises(capability_scenario_verifier.ModelRequiredError):
        capability_scenario_verifier.run_capability_gates("P-X", repo_root, None)

    assert not author_log.exists()
    assert not endpoint_log.exists()
    assert not run_log.exists()

    after = snapshot(repo_root)
    assert after == before
    assert not (repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json").exists()