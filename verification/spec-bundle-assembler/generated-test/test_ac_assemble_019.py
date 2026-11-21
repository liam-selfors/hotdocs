# hotdocs-criterion: sha256:174895bcf69f85d45630edbdc88ab0836e9ebba578dac746a47a6b09f2aa5cb1
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


GEN_TEXT = "Generator guidance text."
TA_TEXT = "Test author guidance text."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(repo_root, slug, comp_id, title, req_id, ac_id, source_path, depends_on, extra_frontmatter):
    cdir = repo_root / "specs" / "components" / slug
    component_md = (
        "---\n"
        + "id: " + comp_id + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: " + source_path + "\n"
        + "depends_on: " + depends_on + "\n"
        + extra_frontmatter
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "Foo doubles a number.\n"
    )
    _write(cdir / "component.md", component_md)
    _write(
        cdir / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        cdir / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n"
        + "\n"
        + "Covers: " + req_id + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given x = 2\n"
        + "When foo(x) is called\n"
        + "Then it returns 4\n"
        + "```\n",
    )
    _write(cdir / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    _write(cdir / "constraints.md", "# Constraints\n\nNone.\n")
    return cdir


def _build_fixture(repo_root):
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** \u2014 a test term.\n")

    foo_dir = _write_component(
        repo_root, "foo", "comp-foo", "Foo", "R-FOO-001", "AC-FOO-001",
        "legacy/foo/", "[comp-kind-javascript]",
        "assets: [javascript:static/app.js]\n",
    )
    _write(
        foo_dir / "interface" / "assets" / "app.js.md",
        "# app.js\n\n```\nexport function double(x)\n```\n",
    )

    _write_component(
        repo_root, "kind-javascript", "comp-kind-javascript", "Kind javascript",
        "R-KJS-001", "AC-KJS-001", "legacy/kind-javascript/", "[]", "",
    )

    sections = ["Layout", "Environment", "Surface", "Running criteria",
                "Strength check", "Test author guidance", "Generator guidance"]
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
    for name in sections:
        definition += "## " + name + "\n\n" + name + " text.\n\n"
    _write(repo_root / "specs" / "architecture" / "asset-kind-javascript.md", definition)

    adapter = (
        "KIND = " + repr("javascript") + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return {" + repr("generator") + ": " + repr(GEN_TEXT + "\n") + ",\n"
        "            " + repr("test_author") + ": " + repr(TA_TEXT + "\n") + "}\n"
    )
    _write(repo_root / "gen" / "kind-javascript" / "kind_javascript.py", adapter)


def _flatten(value):
    if isinstance(value, dict):
        out = []
        for k, v in value.items():
            out.append(str(k))
            out.extend(_flatten(v))
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            out.extend(_flatten(v))
        return out
    if value is None:
        return []
    return [str(value)]


SPEC_FIELDS = ["component_id", "spec_bundle_hash", "spec", "interface", "constraints",
               "dependency_interfaces", "dependency_context", "dependency_usage",
               "vars", "glossary", "hint_code"]


def test_ac_assemble_019(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    spec_linter = _load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    # assemble
    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    interface = field(bundle, "interface")
    assert "export function double(x)" in interface
    assert interface.endswith("\n\n## Asset kind: javascript\n\n" + GEN_TEXT)
    for name in SPEC_FIELDS:
        for text in _flatten(field(bundle, name)):
            assert TA_TEXT not in text, name

    # assemble_criterion, no testing.md
    cb = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    assert field(cb, "testing") == "\n## Asset kind: javascript\n\n" + TA_TEXT
    cb_interface = field(cb, "interface")
    assert "export function double(x)" in cb_interface
    assert GEN_TEXT not in cb_interface

    # with testing.md
    _write(repo_root / "specs" / "components" / "foo" / "testing.md", "Plant X.\n")
    assert spec_linter.lint(None, repo_root).hard_failures == 0
    cb2 = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    assert field(cb2, "testing") == "Plant X.\n\n## Asset kind: javascript\n\n" + TA_TEXT