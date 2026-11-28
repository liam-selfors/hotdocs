# hotdocs-criterion: sha256:28f7ecf00cc76b37ddca9ab9fd2546c65c45ff9dbe02e386e957ee8b9ae8ea58
import dataclasses
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


GENERATOR = "Generator guidance text."
TEST_AUTHOR = "Test author guidance text."


def kind_javascript_files():
    raw = component_files("kind-javascript")
    out = {}
    for rel, text in raw.items():
        rel = rel.replace("R-KIND-JAVASCRIPT-001", "R-KJS-001").replace(
            "AC-KIND-JAVASCRIPT-001", "AC-KJS-001"
        )
        text = (
            text.replace("R-KIND-JAVASCRIPT-001", "R-KJS-001")
            .replace("AC-KIND-JAVASCRIPT-001", "AC-KJS-001")
            .replace("Kind-javascript", "Kind javascript")
        )
        out[rel] = text
    return out


def definition_text():
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
    for name in [
        "Layout",
        "Environment",
        "Surface",
        "Running criteria",
        "Strength check",
        "Test author guidance",
        "Generator guidance",
    ]:
        text += "## " + name + "\n\n" + name + " text.\n\n"
    return text


ADAPTER_SOURCE = (
    "KIND = " + repr("javascript") + "\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return {" + repr("generator") + ": " + repr("Generator guidance text.\n") + ",\n"
    "            " + repr("test_author") + ": " + repr("Test author guidance text.\n") + "}\n"
)


def build_project_kind_fixture(repo_root):
    files = {}
    files.update(
        component_files(
            "foo",
            depends_on="[comp-kind-javascript]",
            extra_frontmatter="assets: [javascript:static/app.js]\n",
        )
    )
    files["specs/components/foo/interface/assets/app.js.md"] = (
        "# app.js\n\n```\nexport function double(x)\n```\n"
    )
    files["specs/architecture/asset-kind-javascript.md"] = definition_text()
    files.update(kind_javascript_files())
    write_fixture(repo_root, files)
    adapter = repo_root / "gen" / "kind-javascript" / "kind_javascript.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(ADAPTER_SOURCE, encoding="utf-8")


def lint_clean(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def all_values(bundle):
    if dataclasses.is_dataclass(bundle):
        return [getattr(bundle, f.name) for f in dataclasses.fields(bundle)]
    if isinstance(bundle, dict):
        return list(bundle.values())
    return list(vars(bundle).values())


def contains_text(value, needle):
    if value is None:
        return False
    if isinstance(value, str):
        return needle in value
    if isinstance(value, dict):
        return any(contains_text(k, needle) or contains_text(v, needle) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return any(contains_text(v, needle) for v in value)
    return needle in str(value)


def test_assemble_appends_generator_guidance_only(tmp_path):
    repo_root = tmp_path
    build_project_kind_fixture(repo_root)
    lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    interface = field(bundle, "interface")
    assert "export function double(x)" in interface
    assert interface.endswith("\n\n## Asset kind: javascript\n\n" + GENERATOR)
    for value in all_values(bundle):
        assert not contains_text(value, TEST_AUTHOR)


def test_assemble_criterion_appends_test_author_guidance_only(tmp_path):
    repo_root = tmp_path
    build_project_kind_fixture(repo_root)
    lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    assert field(bundle, "testing") == "\n## Asset kind: javascript\n\n" + TEST_AUTHOR
    interface = field(bundle, "interface")
    assert "export function double(x)" in interface
    assert GENERATOR not in interface


def test_assemble_criterion_appends_after_testing_md(tmp_path):
    repo_root = tmp_path
    build_project_kind_fixture(repo_root)
    (repo_root / "specs" / "components" / "foo" / "testing.md").write_text(
        "Plant X.\n", encoding="utf-8"
    )
    lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    assert field(bundle, "testing") == "Plant X.\n\n## Asset kind: javascript\n\n" + TEST_AUTHOR