# hotdocs-criterion: sha256:e3c56012156608d9c4a2501334863961bc1cafa164de661da5a65da1c4bab3da
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def component_files(slug, depends_on="[]", extra_frontmatter="", purpose="Foo doubles a number."):
    """The files of one fixture component, keyed by path under repo_root."""
    upper = slug.upper()
    base = f"specs/components/{slug}/"
    return {
        base + "component.md": (
            "---\n"
            f"id: comp-{slug}\n"
            f"title: {slug.capitalize()}\n"
            "status: draft\n"
            "owners: [team-a]\n"
            "sealed: true\n"
            f"source_path: legacy/{slug}/\n"
            f"depends_on: {depends_on}\n"
            + extra_frontmatter +
            "---\n"
            "\n"
            f"# {slug.capitalize()}\n"
            "\n"
            "## Purpose\n"
            "\n"
            f"{purpose}\n"
        ),
        base + f"requirements/R-{upper}-001.md": (
            f"# R-{upper}-001\n"
            "\n"
            f"**R-{upper}-001** — `foo(x)` MUST return `2 * x`.\n"
        ),
        base + f"acceptance/AC-{upper}-001.md": (
            f"# AC-{upper}-001\n"
            "\n"
            f"Covers: R-{upper}-001\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
            "```\n"
        ),
        base + "interface/library.md": "# Library\n\n```\nfoo(x: int) -> int\n```\n",
        base + "constraints.md": "# Constraints\n\nNone.\n",
    }


def write_fixture(repo_root, files):
    files = {"specs/glossary.md": "# Glossary\n\n- **Foo** — a test term.\n", **files}
    for rel, text in files.items():
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ADAPTER_REL = "gen/kind-javascript/kind_javascript.py"
APP_JS_REL = "specs/components/foo/interface/assets/app.js.md"
SECTIONS = [
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
]


def adapter_source(generator_text):
    return (
        "KIND = \"javascript\"\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return {\"generator\": " + repr(generator_text) + ",\n"
        "            \"test_author\": " + repr("Test author guidance text.\n") + "}\n"
    )


def kind_component_files():
    raw = component_files("kind-javascript")
    out = {}
    for rel, text in raw.items():
        new_rel = rel.replace("R-KIND-JAVASCRIPT-001", "R-KJS-001").replace(
            "AC-KIND-JAVASCRIPT-001", "AC-KJS-001"
        )
        new_text = (
            text.replace("R-KIND-JAVASCRIPT-001", "R-KJS-001")
            .replace("AC-KIND-JAVASCRIPT-001", "AC-KJS-001")
            .replace("title: Kind-javascript", "title: Kind javascript")
            .replace("# Kind-javascript", "# Kind javascript")
        )
        out[new_rel] = new_text
    return out


def architecture_doc():
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


def build_project_kind_fixture(repo_root):
    files = component_files(
        "foo",
        depends_on="[comp-kind-javascript]",
        extra_frontmatter="assets: [javascript:static/app.js]\n",
    )
    files[APP_JS_REL] = "# app.js\n\n```\nexport function double(x)\n```\n"
    files["specs/architecture/asset-kind-javascript.md"] = architecture_doc()
    files.update(kind_component_files())
    write_fixture(repo_root, files)
    adapter = repo_root / ADAPTER_REL
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(adapter_source("Generator guidance text.\n"), encoding="utf-8")


def lint_fixture(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def test_adapter_generator_guidance_change_changes_hash(tmp_path):
    repo_root = tmp_path
    build_project_kind_fixture(repo_root)
    lint_fixture(repo_root)

    first = field(spec_bundle_assembler.assemble("comp-foo", repo_root), "spec_bundle_hash")

    adapter = repo_root / ADAPTER_REL
    original = adapter.read_text(encoding="utf-8")
    assert "Generator guidance text." in original
    adapter.write_text(
        original.replace("Generator guidance text.", "Other text."), encoding="utf-8"
    )

    second = field(spec_bundle_assembler.assemble("comp-foo", repo_root), "spec_bundle_hash")

    assert isinstance(first, str) and first.startswith("sha256:")
    assert isinstance(second, str) and second.startswith("sha256:")
    assert first != second


def test_asset_interface_change_changes_hash(tmp_path):
    repo_root = tmp_path
    build_project_kind_fixture(repo_root)
    lint_fixture(repo_root)

    first = field(spec_bundle_assembler.assemble("comp-foo", repo_root), "spec_bundle_hash")

    app_js = repo_root / APP_JS_REL
    original = app_js.read_text(encoding="utf-8")
    assert "double" in original
    app_js.write_text(original.replace("double", "triple"), encoding="utf-8")

    second = field(spec_bundle_assembler.assemble("comp-foo", repo_root), "spec_bundle_hash")

    assert isinstance(first, str) and first.startswith("sha256:")
    assert isinstance(second, str) and second.startswith("sha256:")
    assert first != second