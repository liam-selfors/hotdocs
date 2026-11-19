# hotdocs-criterion: sha256:70b55b5569f61107eac2d5c5245e88eb38337a7c06f7fe25219eb603f4bf24a7
import os
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_mapping(report):
    if isinstance(report, dict):
        return report
    if hasattr(report, "items") and hasattr(report, "keys"):
        return dict(report.items())
    return dict(vars(report))


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def plant_python_adapter(repo_root):
    src = (
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n"
    )
    write(Path(repo_root) / "gen" / "kind-python" / "kind_python.py", src)


def plant_fake_dependencies(repo_root):
    author_src = (
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    cid = bundle[\"criterion_id\"]\n"
        "    return {\n"
        "        \"component_id\": \"comp-unused\",\n"
        "        \"criterion_id\": cid,\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"prompt_version\": \"v1\",\n"
        "        \"cache_hit\": False,\n"
        "        \"file\": {\"path\": \"verification/capabilities/P-X/generated-test/test_cs_x_001.py\",\n"
        "                 \"content\": \"def test_x():\\n    assert True\\n\"},\n"
        "        \"model_call_error\": None,\n"
        "        \"repair_attempts\": 0,\n"
        "        \"probe_findings\": [],\n"
        "    }\n"
    )
    write(Path(repo_root) / "gen" / "test-author" / "test_author.py", author_src)
    endpoint_src = (
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": \"PASS\", \"model\": model, \"backend\": \"fake\",\n"
        "            \"model_call_error\": None}\n"
    )
    write(Path(repo_root) / "gen" / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


def component_md(slug, realizes, sealed, source_path=None):
    lines = [
        "---",
        "id: comp-" + slug,
        "title: " + slug.capitalize() + " component",
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
        "realizes: [" + ", ".join(realizes) + "]",
        "sealed: " + ("true" if sealed else "false"),
    ]
    if source_path is not None:
        lines.append("source_path: " + source_path)
    lines.append("---")
    lines.append("")
    lines.append("# " + slug)
    lines.append("")
    return "\n".join(lines)


def capability_md(pid, title, scenario_id, kind, gherkin_lines):
    lines = [
        "---",
        "id: " + pid,
        "title: " + title,
        "status: draft",
        "owners: [pipeline-team]",
        "---",
        "",
        "# " + title,
        "",
        "### " + scenario_id,
        "",
        "Covers: " + pid,
        "Kind: " + kind,
        "",
        "```gherkin",
    ]
    lines.extend(gherkin_lines)
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def test_report_keys_only_intersecting_capability(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_python_adapter(repo_root)
    plant_fake_dependencies(repo_root)

    write(repo_root / "specs" / "components" / "foo" / "component.md",
          component_md("foo", ["P-ZERO-EDIT"], False))
    write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")
    write(repo_root / "specs" / "components" / "bar" / "component.md",
          component_md("bar", [], False))
    write(repo_root / "gen" / "bar" / "bar.py", "VALUE = 2\n")

    write(repo_root / "specs" / "product" / "zero-edit.md",
          capability_md("P-ZERO-EDIT", "Zero edit", "CS-ZERO-EDIT-001", "llm-judge",
                        ["Given a spec change",
                         "When the pipeline runs",
                         "Then no hand edit is needed"]))
    write(repo_root / "specs" / "product" / "unrelated.md",
          capability_md("P-UNRELATED", "Unrelated", "CS-UNRELATED-001", "llm-judge",
                        ["Given something else",
                         "When it happens",
                         "Then nothing relevant occurs"]))

    def judge(bundle):
        return {"result": "pass", "rationale": "ok"}

    def test_author(bundle):
        return {"model_call_error": None,
                "file": {"path": "verification/capabilities/P-ZERO-EDIT/generated-test/test_cs_zero_edit_001.py",
                         "content": "def test_x():\n    assert True\n"}}

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo", "comp-bar"], repo_root, judge=judge, test_author=test_author)

    mapping = as_mapping(report)
    assert sorted(mapping.keys()) == ["P-ZERO-EDIT"]
    assert "P-UNRELATED" not in mapping


def test_sealed_component_code_directory_is_source_path(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_python_adapter(repo_root)
    plant_fake_dependencies(repo_root)

    write(repo_root / "specs" / "components" / "baz" / "component.md",
          component_md("baz", ["P-SEALED"], True, source_path="pipeline/baz/"))
    write(repo_root / "pipeline" / "baz" / "baz.py",
          "SEALED_MARKER = " + repr("sealed-baz-ok") + "\n")
    assert not (repo_root / "gen" / "baz").exists()

    write(repo_root / "specs" / "product" / "sealed.md",
          capability_md("P-SEALED", "Sealed", "CS-SEALED-001", "generated-test",
                        ["Given the sealed component's code",
                         "When a test imports it",
                         "Then the import succeeds"]))

    log_path = tmp_path / "author_calls.log"
    test_content = (
        "import baz\n"
        "\n"
        "\n"
        "def test_imports_sealed_code():\n"
        "    assert baz.SEALED_MARKER == " + repr("sealed-baz-ok") + "\n"
    )

    def test_author(bundle):
        with open(log_path, "a") as fh:
            fh.write("called\n")
        return {"model_call_error": None,
                "file": {"path": "verification/capabilities/P-SEALED/generated-test/test_cs_sealed_001.py",
                         "content": test_content}}

    def judge(bundle):
        return {"result": "pass", "rationale": "ok"}

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-baz"], repo_root, judge=judge, test_author=test_author)

    assert log_path.is_file()
    assert log_path.read_text().count("called") >= 1

    mapping = as_mapping(report)
    assert "P-SEALED" in mapping
    entry = mapping["P-SEALED"]
    scenarios = field(entry, "scenarios")
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert field(scenario, "id") == "CS-SEALED-001"
    assert field(scenario, "kind") == "generated-test"
    assert field(scenario, "result") == "pass"
    assert field(entry, "overall") == "pass"