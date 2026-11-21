# hotdocs-criterion: sha256:f527c0508af6740343a4adf6c85d3971c6fd86e863422f6cc661d6be39bebf07
import dataclasses
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
MISSING_TESTING_TEXT = "Uses: `specs/architecture/missing.md`\n\nPlant X.\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def write(repo_root, rel, text):
    p = repo_root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))


def build_fixture(repo_root, testing_text=None, with_fix=True):
    write(repo_root, "specs/glossary.md",
          "# Glossary\n\n- **Foo** — a test term.\n")
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
    write(repo_root, "specs/components/foo/constraints.md",
          "# Constraints\n\nNone.\n")
    if with_fix:
        write(repo_root, "specs/architecture/fix.md", F)
    if testing_text is not None:
        write(repo_root, "specs/components/foo/testing.md", testing_text)


def all_text(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return "\n".join(
            all_text(getattr(value, f.name)) for f in dataclasses.fields(value)
        )
    if isinstance(value, dict):
        return "\n".join(
            all_text(k) + "\n" + all_text(v) for k, v in value.items()
        )
    if isinstance(value, (list, tuple)):
        return "\n".join(all_text(v) for v in value)
    if value is None:
        return ""
    return str(value)


def test_testing_includes_uses_documents_and_never_reaches_spec_bundle(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, testing_text=TESTING_TEXT)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )
    expected = TESTING_TEXT + "\n## Uses: specs/architecture/fix.md\n\n" + F
    assert field(bundle, "testing") == expected

    spec_bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    text = all_text(spec_bundle)
    assert "Plant X." not in text
    assert "Fixture rules." not in text


def test_testing_is_empty_without_testing_md(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, testing_text=None)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )
    assert field(bundle, "testing") == ""


def test_missing_uses_document_raises_precondition_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, testing_text=MISSING_TESTING_TEXT)

    with pytest.raises(Exception) as excinfo:
        spec_bundle_assembler.assemble_criterion(
            "comp-foo", "AC-FOO-001", repo_root
        )
    names = [c.__name__ for c in type(excinfo.value).__mro__]
    assert "PreconditionFailure" in names
    expected_cls = getattr(spec_bundle_assembler, "PreconditionFailure", None)
    if expected_cls is not None:
        assert isinstance(excinfo.value, expected_cls)