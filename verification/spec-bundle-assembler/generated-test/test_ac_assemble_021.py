# hotdocs-criterion: sha256:2f63b30c7ef75a08aaca57adb4b9d73cff493c0fcc477db0d80776f57ce053aa
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


def _load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


ADAPTER_SOURCE = (
    'KIND = "javascript"\n'
    "\n"
    "\n"
    "def guidance():\n"
    '    return {"generator": "Generator guidance text.\\n",\n'
    '            "test_author": "Test author guidance text.\\n"}\n'
)


def _component_md(comp_id, title, purpose, source_path, depends_on, assets_line):
    text = (
        "---\n"
        + "id: " + comp_id + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: " + source_path + "\n"
        + "depends_on: " + depends_on + "\n"
    )
    if assets_line:
        text += assets_line + "\n"
    text += (
        "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + purpose + "\n"
    )
    return text


def _write_component(comp_dir, comp_id, title, purpose, source_path, depends_on,
                     assets_line, req_id, ac_id):
    _write(comp_dir / "component.md",
           _component_md(comp_id, title, purpose, source_path, depends_on, assets_line))
    _write(comp_dir / "requirements" / (req_id + ".md"),
           "# " + req_id + "\n\n**" + req_id + "** \u2014 `foo(x)` MUST return `2 * x`.\n")
    _write(comp_dir / "acceptance" / (ac_id + ".md"),
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
    _write(comp_dir / "interface" / "library.md",
           "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")


def _build_fixture(repo_root):
    _write(repo_root / "specs" / "glossary.md",
           "# Glossary\n\n- **Foo** \u2014 a test term.\n")

    foo = repo_root / "specs" / "components" / "foo"
    _write_component(foo, "comp-foo", "Foo", "Foo doubles a number.",
                     "legacy/foo/", "[comp-kind-javascript]",
                     "assets: [javascript:static/app.js]",
                     "R-FOO-001", "AC-FOO-001")
    _write(foo / "interface" / "assets" / "app.js.md",
           "# app.js\n\n```\nexport function double(x)\n```\n")

    kjs = repo_root / "specs" / "components" / "kind-javascript"
    _write_component(kjs, "comp-kind-javascript", "Kind javascript",
                     "Kind javascript doubles a number.",
                     "legacy/kind-javascript/", "[]", None,
                     "R-KJS-001", "AC-KJS-001")

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

    _write(repo_root / "gen" / "kind-javascript" / "kind_javascript.py", ADAPTER_SOURCE)


def _lint_clean(repo_root):
    spec_linter = _load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def _replace(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")
    assert new in path.read_text(encoding="utf-8")


def test_hash_changes_when_adapter_guidance_changes(tmp_path):
    sys.dont_write_bytecode = True
    repo_root = tmp_path / "repo1"
    _build_fixture(repo_root)
    _lint_clean(repo_root)

    first = field(spec_bundle_assembler.assemble("comp-foo", repo_root), "spec_bundle_hash")

    _replace(repo_root / "gen" / "kind-javascript" / "kind_javascript.py",
             "Generator guidance text.", "Other text.")
    _lint_clean(repo_root)

    second = field(spec_bundle_assembler.assemble("comp-foo", repo_root), "spec_bundle_hash")

    assert isinstance(first, str) and first.startswith("sha256:")
    assert isinstance(second, str) and second.startswith("sha256:")
    assert first != second


def test_hash_changes_when_asset_interface_changes(tmp_path):
    sys.dont_write_bytecode = True
    repo_root = tmp_path / "repo2"
    _build_fixture(repo_root)
    _lint_clean(repo_root)

    first = field(spec_bundle_assembler.assemble("comp-foo", repo_root), "spec_bundle_hash")

    _replace(repo_root / "specs" / "components" / "foo" / "interface" / "assets" / "app.js.md",
             "double", "triple")
    _lint_clean(repo_root)

    second = field(spec_bundle_assembler.assemble("comp-foo", repo_root), "spec_bundle_hash")

    assert isinstance(first, str) and first.startswith("sha256:")
    assert isinstance(second, str) and second.startswith("sha256:")
    assert first != second