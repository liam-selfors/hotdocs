# hotdocs-criterion: sha256:d6b5ea27806c7b593cac238528d3f913a8d074d9f867a3b3b06a392cf6dbf36d
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


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

TESTING_TEXT = "Uses: `specs/architecture/fix.md`\n\nPlant X.\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def write(repo_root, rel, text):
    p = repo_root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_fixture(repo_root, testing_text=None, with_fix=True):
    write(repo_root, "specs/glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    write(
        repo_root,
        "specs/components/foo/component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    write(
        repo_root,
        "specs/components/foo/requirements/R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    write(
        repo_root,
        "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        repo_root,
        "specs/components/foo/interface/library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    write(repo_root, "specs/components/foo/constraints.md", "# Constraints\n\nNone.\n")
    if with_fix:
        write(repo_root, "specs/architecture/fix.md", F)
    if testing_text is not None:
        write(repo_root, "specs/components/foo/testing.md", testing_text)


def test_testing_includes_uses_documents_and_spec_bundle_excludes_them(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, testing_text=TESTING_TEXT)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    expected = (
        "Uses: `specs/architecture/fix.md`\n\nPlant X.\n"
        + "\n## Uses: specs/architecture/fix.md\n\n"
        + F
    )
    assert field(bundle, "testing") == expected

    spec_bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    names = [
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
    ]
    combined = "\n".join(str(field(spec_bundle, n)) for n in names)
    assert "Plant X." not in combined
    assert "Fixture rules." not in combined


def test_testing_is_empty_without_testing_md(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, testing_text=None)

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    assert field(bundle, "testing") == ""


def test_missing_uses_document_raises_precondition_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(
        repo_root,
        testing_text="Uses: `specs/architecture/missing.md`\n\nPlant X.\n",
    )

    with pytest.raises(spec_bundle_assembler.PreconditionFailure):
        spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)