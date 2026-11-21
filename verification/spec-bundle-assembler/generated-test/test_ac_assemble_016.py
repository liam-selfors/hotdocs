# hotdocs-criterion: sha256:10538759b994744cd5c3091fcc7439c26d795ce0e878f161c6817d8e97be84c4
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def build_fixture(repo_root, implements_path):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
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
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
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
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
        "\n"
        "Implements: `" + implements_path + "`\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "specs" / "architecture" / "rules.md", RULES_TEXT)


def check_interface(interface):
    marker = "\n## Implements: specs/architecture/rules.md\n\n"
    full = RULES_TEXT.rstrip()
    needle = marker + full
    idx = interface.find(needle)
    assert idx != -1, "interface lacks the Implements section with the file's full text: " + repr(interface)
    rest = interface[idx + len(needle):]
    assert rest.strip() == "", "unexpected text after the Implements document: " + repr(rest)


def test_implements_document_appended_to_both_bundles(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, "specs/architecture/rules.md")

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    check_interface(field(bundle, "interface"))

    cbundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    check_interface(field(cbundle, "interface"))


def test_missing_implements_path_raises_precondition_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, "specs/architecture/missing.md")

    with pytest.raises(Exception) as excinfo:
        spec_bundle_assembler.assemble("comp-foo", repo_root)
    exc_type = getattr(spec_bundle_assembler, "PreconditionFailure", None)
    if exc_type is not None:
        assert isinstance(excinfo.value, exc_type)
    else:
        assert type(excinfo.value).__name__ == "PreconditionFailure"