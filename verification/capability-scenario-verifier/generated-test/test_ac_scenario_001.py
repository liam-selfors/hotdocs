# hotdocs-criterion: sha256:27c7723521b9bf7bba133857f7dc7f22e1381c265797e68320598a1fcb7605f9
"""AC-SCENARIO-001: a generated-test capability scenario is run and keyed by P-id.

Given a blast radius of two components, and one product capability whose
realizes-set includes both, with exactly one generated-test scenario whose
fake test_author returns a passing test, when run_capability_scenarios is
called with that blast radius, then the scenario's test is run, and the
result is keyed by that capability's P-id, never by either component, with
overall "pass".
"""

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
    if hasattr(report, "to_dict"):
        return set(report.to_dict().keys())
    return set(vars(report).keys())


def report_entry(report, key):
    if isinstance(report, dict) or hasattr(report, "__getitem__"):
        return report[key]
    if hasattr(report, "to_dict"):
        return report.to_dict()[key]
    return vars(report)[key]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _component_md(slug):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
        "\n"
        "A fixture component.\n"
    )


def _build_fixture(repo_root, marker_path, author_log_path):
    # Two non-sealed components, both realizing P-X, each with code under gen/.
    for slug in ("alpha", "beta"):
        _write(repo_root / "specs" / "components" / slug / "component.md",
               _component_md(slug))
        _write(repo_root / "gen" / slug / (slug + ".py"),
               "def value():\n    return 1\n")

    # The product capability, with exactly one generated-test scenario.
    capability = (
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Capability X\n"
        "\n"
        "The system does X.\n"
        "\n"
        "## Scenarios\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the assembled system\n"
        "When X is performed\n"
        "Then X succeeds\n"
        "```\n"
    )
    _write(repo_root / "specs" / "product" / "x.md", capability)

    # The python asset adapter every synthetic repo_root plants.
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, "
        "\"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # Fake test-author module, matching author_test's real signature and shape.
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "GATE_VERSION = \"generated_test@3.0.0\"\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(" + repr(str(author_log_path) + ".module") + ", \"a\") as fh:\n"
        "        fh.write(str(bundle.get(\"criterion_id\")) + \"\\n\")\n"
        "    return {\n"
        "        \"component_id\": None,\n"
        "        \"criterion_id\": bundle.get(\"criterion_id\"),\n"
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

    # Fake llm-endpoint module, matching complete's real signature and shape.
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": \"PASS\", \"model\": model, \"backend\": \"fake\",\n"
        "            \"model_call_error\": None}\n",
    )


def test_ac_scenario_001_generated_test_scenario_keyed_by_capability(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    marker_path = tmp_path / "scenario_test_ran.txt"
    author_log_path = tmp_path / "test_author_calls.log"
    _build_fixture(repo_root, marker_path, author_log_path)

    rel_path = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"
    test_content = (
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    Path(" + repr(str(marker_path)) + ").write_text(\"ran\")\n"
        "    assert True\n"
    )

    def fake_test_author(bundle):
        scenario_id = bundle["scenario_id"] if isinstance(bundle, dict) else getattr(bundle, "scenario_id")
        with open(author_log_path, "a") as fh:
            fh.write(str(scenario_id) + "\n")
        # Mirror the real test-author, which writes the file it reports.
        target = repo_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(test_content)
        return {
            "model_call_error": None,
            "file": {"path": rel_path, "content": test_content},
        }

    def fake_judge(bundle):
        raise AssertionError("judge must not be called for a generated-test scenario")

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-alpha", "comp-beta"],
        repo_root,
        judge=fake_judge,
        test_author=fake_test_author,
    )

    # test_author was dispatched exactly once, for the one scenario.
    assert author_log_path.is_file(), "test_author was never called"
    calls = [line for line in author_log_path.read_text().splitlines() if line.strip()]
    assert calls == ["CS-X-001"]

    # The authored test was actually run.
    assert marker_path.is_file(), "the scenario's generated test was not run"
    assert marker_path.read_text() == "ran"

    # Keyed by the capability's P-id, never by either component.
    keys = report_keys(report)
    assert keys == {"P-X"}
    for component_key in ("comp-alpha", "comp-beta", "alpha", "beta"):
        assert component_key not in keys

    entry = report_entry(report, "P-X")
    assert field(entry, "overall") == "pass"

    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert field(scenario, "id") == "CS-X-001"
    assert field(scenario, "kind") == "generated-test"
    assert field(scenario, "result") == "pass"