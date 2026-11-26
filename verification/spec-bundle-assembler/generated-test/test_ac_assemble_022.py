# hotdocs-criterion: sha256:0cc8436124695a34d4da7ca08b4389465d48fdb432b450f606fd390340de9eac
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


def _load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


FOO_CODE = "def foo(x):\n    return 2 * x\n"


def _build(repo_root):
    files = {}
    files.update(component_files("foo"))
    files.update(component_files("baz", depends_on="[comp-foo]"))
    write_fixture(repo_root, files)
    foo_py = repo_root / "legacy" / "foo" / "foo.py"
    foo_py.parent.mkdir(parents=True, exist_ok=True)
    foo_py.write_text(FOO_CODE, encoding="utf-8")
    spec_linter = _load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0
    return foo_py


def _parts(bundle):
    parts = field(bundle, "spec_bundle_parts")
    return field(parts, "spec"), field(parts, "dependency_code")


def test_dependency_code_change_changes_only_dependency_code(tmp_path):
    repo_root = tmp_path
    foo_py = _build(repo_root)

    first = spec_bundle_assembler.assemble("comp-baz", repo_root)
    first_hash = field(first, "spec_bundle_hash")
    first_spec, first_dep = _parts(first)

    foo_py.write_text(FOO_CODE.replace("2 * x", "x + x"), encoding="utf-8")
    assert foo_py.read_text(encoding="utf-8") == "def foo(x):\n    return x + x\n"

    second = spec_bundle_assembler.assemble("comp-baz", repo_root)
    second_hash = field(second, "spec_bundle_hash")
    second_spec, second_dep = _parts(second)

    assert first_hash != second_hash
    assert first_spec == second_spec
    assert first_dep != second_dep


def test_requirement_change_changes_only_spec(tmp_path):
    repo_root = tmp_path
    _build(repo_root)

    first = spec_bundle_assembler.assemble("comp-baz", repo_root)
    first_spec, first_dep = _parts(first)

    req = repo_root / "specs" / "components" / "baz" / "requirements" / "R-BAZ-001.md"
    text = req.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    req.write_text(text + "Note.\n", encoding="utf-8")

    second = spec_bundle_assembler.assemble("comp-baz", repo_root)
    second_spec, second_dep = _parts(second)

    assert first_spec != second_spec
    assert first_dep == second_dep