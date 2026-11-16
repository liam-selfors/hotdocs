import spec_bundle_assembler

import importlib.util
import sys
from pathlib import Path

import pytest


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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _load_spec_linter():
    gen = next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path, implements_path: str) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
    )

    comp = repo_root / "specs" / "components" / "foo"
    _write(
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
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
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
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
        "\n"
        "Implements: `" + implements_path + "`\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )

    _write(repo_root / "specs" / "architecture" / "rules.md", RULES_TEXT)

    _write(
        repo_root / "legacy" / "foo" / "foo.py",
        "def foo(x: int) -> int:\n"
        "    return 2 * x\n",
    )


MARKER = "\n## Implements: specs/architecture/rules.md\n\n"


def _assert_appended(interface: str) -> None:
    assert isinstance(interface, str)
    idx = interface.find(MARKER)
    assert idx != -1, f"marker not found in interface: {interface!r}"
    rest = interface[idx + len(MARKER):]
    # Immediately followed by the file's full text...
    assert rest.startswith(RULES_TEXT.rstrip()), (
        f"text after marker is not the file's full text: {rest!r}"
    )
    # ...and nothing but whitespace after it.
    assert rest.rstrip() == RULES_TEXT.rstrip()
    assert rest[len(RULES_TEXT.rstrip()):].strip() == ""


def test_implements_document_appended_to_both_bundles(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, "specs/architecture/rules.md")

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    _assert_appended(field(bundle, "interface"))

    cbundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )
    _assert_appended(field(cbundle, "interface"))


def test_implements_missing_path_raises_precondition_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, "specs/architecture/missing.md")

    with pytest.raises(spec_bundle_assembler.PreconditionFailure):
        spec_bundle_assembler.assemble("comp-foo", repo_root)