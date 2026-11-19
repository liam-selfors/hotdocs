# hotdocs-criterion: sha256:4d83b18298c4cc85d117af2de9726d69633c39dbfc51f576d6e7d6afbd6c4713
import dataclasses
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, source_path, depends_on, assets_line):
    text = (
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: " + source_path + "\n"
        "depends_on: " + depends_on + "\n"
    )
    if assets_line:
        text += assets_line + "\n"
    text += (
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n"
    )
    return text


def _build_component(root, slug, comp_id, title, source_path, depends_on,
                     assets_line, req_id, ac_id):
    base = root / "specs" / "components" / slug
    _write(base / "component.md",
           _component_md(comp_id, title, source_path, depends_on, assets_line))
    _write(base / "requirements" / (req_id + ".md"),
           "# " + req_id + "\n"
           "\n"
           "**" + req_id + "** \u2014 `foo(x)` MUST return `2 * x`.\n")
    _write(base / "acceptance" / (ac_id + ".md"),
           "# " + ac_id + "\n"
           "\n"
           "Covers: " + req_id + "\n"
           "Kind: generated-test\n"
           "\n"
           "```gherkin\n"
           "Given x = 2\n"
           "When foo(x) is called\n"
           "Then it returns 4\n"
           "```\n")
    _write(base / "interface" / "library.md",
           "# Library\n"
           "\n"
           "```\n"
           "foo(x: int) -> int\n"
           "```\n")
    _write(base / "constraints.md",
           "# Constraints\n"
           "\n"
           "None.\n")
    return base


def _build_fixture(repo_root):
    _write(repo_root / "specs" / "glossary.md",
           "# Glossary\n"
           "\n"
           "- **Foo** \u2014 a test term.\n")

    foo = _build_component(
        repo_root, "foo", "comp-foo", "Foo", "legacy/foo/",
        "[comp-kind-javascript]", "assets: [javascript:static/app.js]",
        "R-FOO-001", "AC-FOO-001")
    _write(foo / "interface" / "assets" / "app.js.md",
           "# app.js\n"
           "\n"
           "```\n"
           "export function double(x)\n"
           "```\n")

    _build_component(
        repo_root, "kind-javascript", "comp-kind-javascript", "Kind javascript",
        "legacy/kind-javascript/", "[]", None, "R-KJS-001", "AC-KJS-001")

    definition = (
        "---\n"
        "id: kind-javascript\n"
        "title: Asset kind javascript\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Asset kind javascript\n"
        "\n"
    )
    for name in ["Layout", "Environment", "Surface", "Running criteria",
                 "Strength check", "Test author guidance", "Generator guidance"]:
        definition += "## " + name + "\n\n" + name + " text.\n\n"
    _write(repo_root / "specs" / "architecture" / "asset-kind-javascript.md",
           definition)

    _write(repo_root / "gen" / "kind-javascript" / "kind_javascript.py",
           'KIND = "javascript"\n'
           "\n"
           "\n"
           "def guidance():\n"
           '    return {"generator": "Generator guidance text.\\n",\n'
           '            "test_author": "Test author guidance text.\\n"}\n')
    return foo


def _lint_clean(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents
               if p.name == "gen")
    base = gen / "spec-linter"
    path = (base / "spec_linter.py" if (base / "spec_linter.py").is_file()
            else base / "spec_linter" / "__init__.py")
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def _strings(value):
    if value is None:
        return
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            yield from _strings(v)
    elif dataclasses.is_dataclass(value):
        for f in dataclasses.fields(value):
            yield from _strings(getattr(value, f.name))
    else:
        yield str(value)


def test_ac_assemble_019_project_kind_guidance(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    foo = _build_fixture(repo_root)
    _lint_clean(repo_root)

    # assemble
    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    interface = field(bundle, "interface")
    assert "export function double(x)" in interface
    assert interface.endswith(
        "\n\n## Asset kind: javascript\n\nGenerator guidance text.")
    for text in _strings(bundle):
        assert "Test author guidance text." not in text

    # assemble_criterion, no testing.md
    cbundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root)
    assert field(cbundle, "testing") == (
        "\n## Asset kind: javascript\n\nTest author guidance text.")
    cinterface = field(cbundle, "interface")
    assert "export function double(x)" in cinterface
    assert "Generator guidance text." not in cinterface

    # with testing.md
    _write(foo / "testing.md", "Plant X.\n")
    cbundle2 = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root)
    assert field(cbundle2, "testing") == (
        "Plant X.\n\n## Asset kind: javascript\n\nTest author guidance text.")