# hotdocs-criterion: sha256:f9493403405c477aa67f3c1cd7bc734b9144ee85c7810fcc5940d6912018d404
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def report_keys(report):
    if hasattr(report, "keys"):
        return sorted(report.keys())
    return sorted(vars(report).keys())


def report_entry(report, key):
    if hasattr(report, "keys"):
        return report[key]
    return getattr(report, key)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def plant_python_adapter(repo_root):
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )


def write_component(repo_root, slug, realizes=None, sealed=False, source_path=None):
    lines = [
        "---",
        "id: comp-" + slug,
        "title: " + slug.capitalize() + " component",
        "status: draft",
        "owners: [pipeline-team]",
    ]
    if realizes is not None:
        lines.append("realizes: [" + ", ".join(realizes) + "]")
    if sealed:
        lines.append("sealed: true")
        lines.append("source_path: " + source_path)
    else:
        lines.append("sealed: false")
    lines.append("---")
    lines.append("")
    lines.append("# " + slug.capitalize())
    lines.append("")
    lines.append("A fixture component.")
    lines.append("")
    write(repo_root / "specs" / "components" / slug / "component.md", "\n".join(lines))


def write_capability(repo_root, name, cap_id, scenario_suffix, kind):
    text = (
        "---\n"
        "id: " + cap_id + "\n"
        "title: " + name + " capability\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# " + name + "\n"
        "\n"
        "### CS-" + scenario_suffix + "-001\n"
        "\n"
        "Covers: " + cap_id + "\n"
        "Kind: " + kind + "\n"
        "\n"
        "```gherkin\n"
        "Given a fixture component\n"
        "When the capability is exercised\n"
        "Then it behaves as described\n"
        "```\n"
    )
    write(repo_root / "specs" / "product" / (name + ".md"), text)


def test_report_keys_only_intersecting_capability(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_python_adapter(repo_root)

    write_component(repo_root, "foo", realizes=["P-ZERO-EDIT"])
    write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")
    write_component(repo_root, "bar")
    write(repo_root / "gen" / "bar" / "bar.py", "VALUE = 2\n")
    # P-UNRELATED is realized only by a component outside the blast radius.
    write_component(repo_root, "qux", realizes=["P-UNRELATED"])
    write(repo_root / "gen" / "qux" / "qux.py", "VALUE = 3\n")

    write_capability(repo_root, "zero-edit", "P-ZERO-EDIT", "ZERO-EDIT", "llm-judge")
    write_capability(repo_root, "unrelated", "P-UNRELATED", "UNRELATED", "llm-judge")

    log = tmp_path / "judge.log"

    def judge(bundle):
        with open(log, "a") as fh:
            fh.write(str(field(bundle, "capability_id")) + "\n")
        return {"result": "pass", "rationale": "looks right"}

    def test_author(bundle):
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo", "comp-bar"], repo_root, judge=judge, test_author=test_author
    )

    assert report_keys(report) == ["P-ZERO-EDIT"]
    if log.exists():
        assert "P-UNRELATED" not in log.read_text().split()


def test_sealed_component_code_directory_is_source_path(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_python_adapter(repo_root)

    write_component(
        repo_root, "baz", realizes=["P-SEALED"], sealed=True, source_path="pipeline/baz/"
    )
    write(
        repo_root / "pipeline" / "baz" / "baz_sealed_mod.py",
        "MARKER = " + repr("sealed-code-here") + "\n",
    )
    assert not (repo_root / "gen" / "baz").exists()

    write_capability(repo_root, "sealed", "P-SEALED", "SEALED", "generated-test")

    log = tmp_path / "author.log"
    test_content = (
        "import baz_sealed_mod\n"
        "\n"
        "\n"
        "def test_imports_sealed_code():\n"
        "    assert baz_sealed_mod.MARKER == " + repr("sealed-code-here") + "\n"
    )

    def test_author(bundle):
        with open(log, "a") as fh:
            fh.write(str(field(bundle, "scenario_id")) + "\n")
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-SEALED/generated-test/test_cs_sealed_001.py",
                "content": test_content,
            },
        }

    def judge(bundle):
        return {"result": "pass", "rationale": "unused"}

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-baz"], repo_root, judge=judge, test_author=test_author
    )

    assert report_keys(report) == ["P-SEALED"]
    assert log.exists() and "CS-SEALED-001" in log.read_text().split()
    entry = report_entry(report, "P-SEALED")
    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert field(scenario, "id") == "CS-SEALED-001"
    assert field(scenario, "result") == "pass"
    assert field(entry, "overall") == "pass"