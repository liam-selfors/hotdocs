# hotdocs-criterion: sha256:7d3243aae3585ae96aaf5bfd9b7a94a98a31a16febda3cabba405b9f947c8a8f
import shutil
from pathlib import Path

import pytest

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
    if isinstance(report, dict):
        return report[key]
    if hasattr(report, "__getitem__"):
        return report[key]
    return getattr(report, key)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _copy_real_compiler(repo_root):
    try:
        gen = next(
            p
            for p in Path(capability_scenario_verifier.__file__).resolve().parents
            if p.name == "gen"
        )
    except StopIteration:
        return
    src = gen.parent / "pipeline" / "criterion-compiler"
    if src.is_dir():
        shutil.copytree(
            src,
            repo_root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )


def _write_fake_dependencies(repo_root, log_path):
    test_author_src = (
        "def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('module_author_test ' + str(bundle['criterion_id']) + '\\n')\n"
        "    cid = str(bundle['criterion_id'])\n"
        "    name = 'test_' + cid.lower().replace('-', '_') + '.py'\n"
        "    return {\n"
        "        'component_id': '',\n"
        "        'criterion_id': cid,\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {\n"
        "            'path': 'verification/capabilities/fake/generated-test/' + name,\n"
        "            'content': 'def test_x():\\n    assert True\\n',\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", test_author_src)

    llm_src = (
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('module_complete\\n')\n"
        "    return {\n"
        "        'text': 'pass',\n"
        "        'model': model,\n"
        "        'backend': 'fake',\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", llm_src)


def _write_component(repo_root, slug, realizes=None, sealed=False, source_path=None):
    upper = slug.upper()
    lines = [
        "---",
        "id: comp-" + slug,
        "title: " + slug.capitalize() + " component",
        "status: draft",
        "owners: [tester]",
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
    lines.append("# " + slug)
    lines.append("")
    comp_dir = repo_root / "specs" / "components" / slug
    _write(comp_dir / "component.md", "\n".join(lines) + "\n")
    _write(
        comp_dir / "requirements" / ("R-" + upper + "-001.md"),
        "**R-" + upper + "-001** - The component MUST exist.\n",
    )
    _write(
        comp_dir / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\nCovers: R-" + upper + "-001\nKind: llm-judge\n\n"
        "```gherkin\nGiven the component\nWhen it is inspected\nThen it exists\n```\n",
    )


def _write_capability(repo_root, name, cap_id, scenario_suffix):
    text = (
        "---\n"
        "id: " + cap_id + "\n"
        "title: " + cap_id + " capability\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n"
        "\n"
        "# " + cap_id + "\n"
        "\n"
        "### CS-" + scenario_suffix + "-001\n"
        "\n"
        "Covers: " + cap_id + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a repository\n"
        "When the capability is exercised\n"
        "Then it works\n"
        "```\n"
    )
    _write(repo_root / "specs" / "product" / (name + ".md"), text)


def _make_test_author(log_path, content_by_cap):
    def test_author(bundle):
        cap = bundle["capability_id"]
        sid = bundle["scenario_id"]
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("injected " + str(cap) + " " + str(sid) + "\n")
        name = "test_" + str(sid).lower().replace("-", "_") + ".py"
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/" + str(cap) + "/generated-test/" + name,
                "content": content_by_cap.get(cap, "def test_x():\n    assert True\n"),
            },
        }

    return test_author


def test_report_keyed_only_by_capability_realized_within_blast_radius(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _copy_real_compiler(repo_root)
    _write_fake_dependencies(repo_root, log_path)

    _write_component(repo_root, "foo", realizes=["P-ZERO-EDIT"])
    _write(repo_root / "gen" / "foo" / "foo.py", "def value():\n    return 1\n")
    _write_component(repo_root, "bar")
    _write(repo_root / "gen" / "bar" / "bar.py", "def value():\n    return 2\n")

    _write_capability(repo_root, "zero-edit", "P-ZERO-EDIT", "ZERO-EDIT")
    _write_capability(repo_root, "unrelated", "P-UNRELATED", "UNRELATED")

    test_author = _make_test_author(log_path, {})
    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo", "comp-bar"], repo_root, judge=None, test_author=test_author
    )

    assert report_keys(report) == {"P-ZERO-EDIT"}


def test_sealed_component_code_directory_is_its_source_path(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _copy_real_compiler(repo_root)
    _write_fake_dependencies(repo_root, log_path)

    _write_component(
        repo_root, "baz", realizes=["P-SEALED"], sealed=True, source_path="pipeline/baz/"
    )
    _write(
        repo_root / "pipeline" / "baz" / "baz.py",
        "def sealed_marker():\n    return 'sealed-baz-ok'\n",
    )
    assert not (repo_root / "gen" / "baz").exists()

    _write_capability(repo_root, "sealed", "P-SEALED", "SEALED")

    content = (
        "import baz\n"
        "\n"
        "\n"
        "def test_imports_sealed_code():\n"
        "    assert baz.sealed_marker() == " + repr("sealed-baz-ok") + "\n"
    )
    test_author = _make_test_author(log_path, {"P-SEALED": content})

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-baz"], repo_root, judge=None, test_author=test_author
    )

    assert log_path.is_file()
    assert "injected P-SEALED" in log_path.read_text(encoding="utf-8")

    assert report_keys(report) == {"P-SEALED"}
    entry = report_entry(report, "P-SEALED")
    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 1
    assert field(scenarios[0], "id") == "CS-SEALED-001"
    assert field(scenarios[0], "result") == "pass"
    assert field(entry, "overall") == "pass"