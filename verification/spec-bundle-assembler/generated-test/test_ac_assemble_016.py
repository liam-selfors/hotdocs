import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


RULES_TEXT = (
    "---\n"
    "id: arch-rules\n"
    "title: Rules\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Rules\n"
    "\n"
    "Foo rounds down.\n"
)

GLOSSARY_TEXT = (
    "# Glossary\n"
    "\n"
    "- **Foo** — a test term.\n"
)

COMPONENT_TEXT = (
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
    "Foo doubles a number.\n"
)

REQUIREMENT_TEXT = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
)

ACCEPTANCE_TEXT = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

CONSTRAINTS_TEXT = (
    "# Constraints\n"
    "\n"
    "None.\n"
)


def _library_text(implements_path):
    return (
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
        "\n"
        "Implements: `" + implements_path + "`\n"
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root, implements_path, write_rules=True):
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_TEXT)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_TEXT)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_TEXT)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_TEXT)
    _write(comp / "interface" / "library.md", _library_text(implements_path))
    _write(comp / "constraints.md", CONSTRAINTS_TEXT)
    if write_rules:
        _write(repo_root / "specs" / "architecture" / "rules.md", RULES_TEXT)


def _load_spec_linter():
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


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _assert_implements_appended(interface):
    assert isinstance(interface, str), interface
    marker = "\n## Implements: specs/architecture/rules.md\n\n"
    idx = interface.find(marker)
    assert idx != -1, "marker not found in interface: %r" % interface
    after = interface[idx + len(marker):]
    expected = RULES_TEXT.rstrip()
    assert after.startswith(expected), (
        "interface after marker does not start with rules.md full text: %r" % after
    )
    assert after[len(expected):].strip() == "", (
        "non-whitespace content after appended document: %r" % after[len(expected):]
    )


def test_implements_document_appended_to_both_bundles(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, "specs/architecture/rules.md")

    spec_linter = _load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    _assert_implements_appended(_field(bundle, "interface"))

    cbundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    _assert_implements_appended(_field(cbundle, "interface"))


def test_missing_implements_path_raises_precondition_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, "specs/architecture/missing.md", write_rules=True)

    with pytest.raises(Exception) as excinfo:
        spec_bundle_assembler.assemble("comp-foo", repo_root)

    names = [cls.__name__ for cls in type(excinfo.value).__mro__]
    assert "PreconditionFailure" in names, (
        "expected PreconditionFailure, got %r" % (excinfo.value,)
    )
    expected_cls = getattr(spec_bundle_assembler, "PreconditionFailure", None)
    if expected_cls is not None:
        assert isinstance(excinfo.value, expected_cls)