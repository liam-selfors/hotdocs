# hotdocs-criterion: sha256:7dfca5a0f06c74b26f82f032c59e00185a34e7472d6d82ba020d91fe3173e24b
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


def load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    if (base / "spec_linter.py").is_file():
        path = base / "spec_linter.py"
    else:
        path = base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

FOO_COMPONENT = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "depends_on: [comp-kind-javascript]\n"
    "assets: [javascript:static/app.js]\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

KJS_COMPONENT = (
    "---\n"
    "id: comp-kind-javascript\n"
    "title: Kind javascript\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/kind-javascript/\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Kind javascript\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)


def requirement(rid):
    return "# " + rid + "\n\n**" + rid + "** \u2014 `foo(x)` MUST return `2 * x`.\n"


def acceptance(aid, rid):
    return (
        "# " + aid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n"
    )


LIBRARY = "# Library\n\n```\nfoo(x: int) -> int\n```\n"
CONSTRAINTS = "# Constraints\n\nNone.\n"

APP_JS_MD = (
    "# app.js\n"
    "\n"
    "```\n"
    "export function double(x)\n"
    "```\n"
)

SECTIONS = [
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
]


def kind_definition():
    text = (
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
    for name in SECTIONS:
        text += "## " + name + "\n\n" + name + " text.\n\n"
    return text


ADAPTER = (
    "KIND = \"javascript\"\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return {\"generator\": \"Generator guidance text.\\n\",\n"
    "            \"test_author\": \"Test author guidance text.\\n\"}\n"
)


def build_component(root, slug, component_md, rid, aid):
    base = "specs/components/" + slug + "/"
    write(root, base + "component.md", component_md)
    write(root, base + "requirements/" + rid + ".md", requirement(rid))
    write(root, base + "acceptance/" + aid + ".md", acceptance(aid, rid))
    write(root, base + "interface/library.md", LIBRARY)
    write(root, base + "constraints.md", CONSTRAINTS)


def build_fixture(root):
    write(root, "specs/glossary.md", GLOSSARY)
    build_component(root, "foo", FOO_COMPONENT, "R-FOO-001", "AC-FOO-001")
    write(root, "specs/components/foo/interface/assets/app.js.md", APP_JS_MD)
    build_component(
        root, "kind-javascript", KJS_COMPONENT, "R-KJS-001", "AC-KJS-001"
    )
    write(root, "specs/architecture/asset-kind-javascript.md", kind_definition())
    write(root, "gen/kind-javascript/kind_javascript.py", ADAPTER)


def lint_clean(root):
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, root).hard_failures == 0


def test_adapter_guidance_change_changes_hash(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    lint_clean(repo_root)

    first = field(
        spec_bundle_assembler.assemble("comp-foo", repo_root), "spec_bundle_hash"
    )

    adapter = repo_root / "gen" / "kind-javascript" / "kind_javascript.py"
    original = adapter.read_text(encoding="utf-8")
    assert "Generator guidance text." in original
    adapter.write_text(
        original.replace("Generator guidance text.", "Other text."),
        encoding="utf-8",
    )

    second = field(
        spec_bundle_assembler.assemble("comp-foo", repo_root), "spec_bundle_hash"
    )

    assert isinstance(first, str) and first
    assert isinstance(second, str) and second
    assert first != second


def test_asset_interface_change_changes_hash(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    lint_clean(repo_root)

    first = field(
        spec_bundle_assembler.assemble("comp-foo", repo_root), "spec_bundle_hash"
    )

    asset_md = (
        repo_root / "specs" / "components" / "foo" / "interface" / "assets"
        / "app.js.md"
    )
    original = asset_md.read_text(encoding="utf-8")
    assert "double" in original
    asset_md.write_text(original.replace("double", "triple"), encoding="utf-8")

    second = field(
        spec_bundle_assembler.assemble("comp-foo", repo_root), "spec_bundle_hash"
    )

    assert isinstance(first, str) and first
    assert isinstance(second, str) and second
    assert first != second