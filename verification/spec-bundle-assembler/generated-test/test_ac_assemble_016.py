# hotdocs-criterion: sha256:4dec2bc8e4c5502e2d4a1a427d215bbef68fc948916f2137cfba5b311a094fc9
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

COMPONENT_MD = (
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

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
)

ACCEPTANCE_MD = (
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

LIBRARY_BASE = (
    "# Library\n"
    "\n"
    "```\n"
    "foo(x: int) -> int\n"
    "```\n"
)

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

RULES_MD = (
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen"
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, implements_path, write_rules=True):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    library = LIBRARY_BASE + "\n" + "Implements: `" + implements_path + "`\n"
    write(comp / "interface" / "library.md", library)
    write(comp / "constraints.md", CONSTRAINTS_MD)
    if write_rules:
        write(repo_root / "specs" / "architecture" / "rules.md", RULES_MD)


def assert_implements_appended(interface, full_text):
    marker = "\n## Implements: specs/architecture/rules.md\n\n"
    assert isinstance(interface, str)
    idx = interface.find(marker)
    assert idx != -1, "marker not found in interface: " + repr(interface)
    rest = interface[idx + len(marker):]
    expected = full_text.rstrip()
    assert rest.startswith(expected), (
        "document text does not immediately follow marker: " + repr(rest)
    )
    assert rest[len(expected):].strip() == "", (
        "unexpected trailing content after document: " + repr(rest[len(expected):])
    )


def test_implements_document_appended_to_both_bundles(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, "specs/architecture/rules.md")

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    full_text = (repo_root / "specs" / "architecture" / "rules.md").read_text(encoding="utf-8")

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    assert_implements_appended(field(bundle, "interface"), full_text)

    cbundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    assert_implements_appended(field(cbundle, "interface"), full_text)


def test_missing_implements_document_raises_precondition_failure(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, "specs/architecture/missing.md")

    precondition_failure = getattr(spec_bundle_assembler, "PreconditionFailure")

    with pytest.raises(precondition_failure):
        spec_bundle_assembler.assemble("comp-foo", repo_root)