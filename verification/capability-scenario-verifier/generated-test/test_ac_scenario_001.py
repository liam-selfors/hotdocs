# hotdocs-criterion: sha256:3142cb3379aec568eb2009d02d7193581e263f239ca1c1d32c7e928f9e47a858
import json
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def report_keys(report):
    if isinstance(report, dict):
        return set(report.keys())
    if hasattr(report, "keys"):
        return set(report.keys())
    return set(vars(report).keys())


def report_entry(report, key):
    if isinstance(report, dict) or hasattr(report, "__getitem__"):
        return report[key]
    return getattr(report, key)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_fixture(repo_root, marker_path):
    # The planted python adapter.
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # Two components, both realizing P-X.
    for slug in ("alpha", "beta"):
        write(
            repo_root / "specs" / "components" / slug / "component.md",
            "---\n"
            "id: comp-" + slug + "\n"
            "title: " + slug.capitalize() + "\n"
            "status: draft\n"
            "owners: [pipeline-team]\n"
            "realizes: [P-X]\n"
            "sealed: false\n"
            "---\n"
            "\n"
            "# " + slug.capitalize() + "\n"
            "\n"
            "A fixture component.\n",
        )
        write(
            repo_root / "gen" / slug / (slug + ".py"),
            "def value():\n    return " + repr(slug) + "\n",
        )

    # One product capability with exactly one generated-test scenario.
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
        "Given the assembled system\n"
        "When the capability is exercised\n"
        "Then it behaves as described\n"
        "```\n",
    )

    # Fake dependency modules at the documented paths (unused here: the
    # injected test_author callable is what dispatches the scenario).
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        \"component_id\": None,\n"
        "        \"criterion_id\": bundle[\"criterion_id\"],\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"prompt_version\": \"v1\",\n"
        "        \"cache_hit\": False,\n"
        "        \"file\": {\n"
        "            \"path\": \"verification/capabilities/P-X/generated-test/test_cs_x_001.py\",\n"
        "            \"content\": \"def test_x():\\n    assert True\\n\",\n"
        "        },\n"
        "        \"model_call_error\": None,\n"
        "        \"repair_attempts\": 0,\n"
        "        \"probe_findings\": [],\n"
        "    }\n",
    )
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": \"PASS\", \"model\": model, \"backend\": \"fake\",\n"
        "            \"model_call_error\": None}\n",
    )


def test_ac_scenario_001_result_keyed_by_capability_with_overall_pass(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    marker_path = tmp_path / "scenario_test_ran.marker"
    log_path = tmp_path / "test_author_calls.log"
    build_fixture(repo_root, marker_path)

    test_content = (
        "def test_x():\n"
        "    with open(" + repr(str(marker_path)) + ", 'a') as fh:\n"
        "        fh.write('ran\\n')\n"
        "    assert True\n"
    )

    def fake_test_author(bundle):
        if isinstance(bundle, dict):
            sid = bundle.get("scenario_id")
            kind = bundle.get("kind")
        else:
            sid = getattr(bundle, "scenario_id", None)
            kind = getattr(bundle, "kind", None)
        with open(log_path, "a") as fh:
            fh.write(json.dumps({"scenario_id": sid, "kind": kind}) + "\n")
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
                "content": test_content,
            },
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-alpha", "comp-beta"], repo_root, test_author=fake_test_author
    )

    # The fake test_author was dispatched exactly once, for the one scenario.
    assert log_path.is_file(), "test_author was never called"
    calls = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    assert len(calls) == 1
    assert calls[0]["scenario_id"] == "CS-X-001"

    # The authored test was actually run.
    assert marker_path.is_file(), "the scenario's test was not run"
    assert "ran" in marker_path.read_text()

    # Keyed by the capability's P-id, never by either component.
    keys = report_keys(report)
    assert keys == {"P-X"}
    assert "comp-alpha" not in keys
    assert "comp-beta" not in keys
    assert "alpha" not in keys
    assert "beta" not in keys

    entry = report_entry(report, "P-X")
    assert field(entry, "overall") == "pass"
    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert field(scenario, "id") == "CS-X-001"
    assert field(scenario, "kind") == "generated-test"
    assert field(scenario, "result") == "pass"