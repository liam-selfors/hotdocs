# hotdocs-criterion: sha256:9c96d7c7f23c918f13f36245b099980a3b5b6bf76940c73ef92f9a7ee87c216b
import importlib.util
import sys
from pathlib import Path

import pytest

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


def lint_clean(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


TESTING = "Uses: `specs/architecture/fix.md`\n\nPlant X.\n"
F = (
    "---\n"
    "id: arch-fix\n"
    "title: Fix\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "Fixture rules.\n"
)

SPEC_BUNDLE_FIELDS = [
    "component_id",
    "spec_bundle_hash",
    "spec",
    "interface",
    "constraints",
    "dependency_interfaces",
    "dependency_context",
    "dependency_usage",
    "vars",
    "glossary",
    "hint_code",
    "spec_bundle_parts",
]


def test_testing_holds_test_spec_and_uses_documents_never_in_spec_bundle(tmp_path):
    files = component_files("foo")
    files["specs/components/foo/testing.md"] = TESTING
    files["specs/architecture/fix.md"] = F
    write_fixture(tmp_path, files)
    lint_clean(tmp_path)

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", tmp_path)
    expected = TESTING + "\n## Uses: specs/architecture/fix.md\n\n" + F
    assert field(bundle, "testing") == expected

    spec_bundle = spec_bundle_assembler.assemble("comp-foo", tmp_path)
    everything = "\n".join(repr(field(spec_bundle, name)) for name in SPEC_BUNDLE_FIELDS)
    assert "Plant X." not in everything
    assert "Fixture rules." not in everything


def test_testing_is_empty_without_testing_md(tmp_path):
    write_fixture(tmp_path, component_files("foo"))
    lint_clean(tmp_path)

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", tmp_path)
    assert field(bundle, "testing") == ""


def test_missing_uses_document_raises_precondition_failure(tmp_path):
    files = component_files("foo")
    files["specs/components/foo/testing.md"] = "Uses: `specs/architecture/missing.md`\n\nPlant X.\n"
    write_fixture(tmp_path, files)

    with pytest.raises(Exception) as excinfo:
        spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", tmp_path)
    names = [cls.__name__ for cls in type(excinfo.value).__mro__]
    assert "PreconditionFailure" in names