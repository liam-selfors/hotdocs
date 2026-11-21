# hotdocs-criterion: sha256:5f80e34ca4270c1560c90cc5efa7dc6813dc04b3839a8b78ef2a19b7a84887d5
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _plant_python_adapter(repo_root):
    src = (
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n"
    )
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", src)


def _plant_component(repo_root, slug):
    module = slug.replace("-", "_")
    text = (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
        "\n"
        "A fixture component.\n"
    )
    _write(repo_root / "specs" / "components" / slug / "component.md", text)
    _write(repo_root / "gen" / slug / (module + ".py"), "VALUE = 1\n")


def _plant_capability(repo_root):
    text = (
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
        "Given a system\n"
        "When it runs\n"
        "Then it works\n"
        "```\n"
    )
    _write(repo_root / "specs" / "product" / "x.md", text)


def test_ac_scenario_001_two_components_one_capability_keyed_by_p_id(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_python_adapter(repo_root)
    _plant_component(repo_root, "alpha")
    _plant_component(repo_root, "beta")
    _plant_capability(repo_root)

    run_log = tmp_path / "test_ran.log"
    author_log = tmp_path / "author_called.log"

    test_content = (
        "def test_x():\n"
        "    with open(" + repr(str(run_log)) + ", 'a') as fh:\n"
        "        fh.write('ran\\n')\n"
        "    assert True\n"
    )

    def fake_test_author(bundle):
        sid = bundle["scenario_id"] if isinstance(bundle, dict) else getattr(bundle, "scenario_id")
        with open(author_log, "a") as fh:
            fh.write(str(sid) + "\n")
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

    # test_author was dispatched for the one scenario
    assert author_log.is_file()
    assert author_log.read_text().splitlines() == ["CS-X-001"]

    # the generated test was actually run
    assert run_log.is_file()
    assert "ran" in run_log.read_text()

    # keyed by the capability's P-id, never by either component
    keys = list(report.keys()) if isinstance(report, dict) else list(vars(report).keys())
    assert keys == ["P-X"]
    for comp in ("comp-alpha", "comp-beta", "alpha", "beta"):
        assert comp not in keys

    entry = report["P-X"] if isinstance(report, dict) else getattr(report, "P-X")
    assert field(entry, "overall") == "pass"
    scenarios = field(entry, "scenarios")
    assert len(scenarios) == 1
    sc = scenarios[0]
    assert field(sc, "id") == "CS-X-001"
    assert field(sc, "kind") == "generated-test"
    assert field(sc, "result") == "pass"