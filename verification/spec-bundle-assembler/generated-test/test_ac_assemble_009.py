import dataclasses
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


EXPECTED_FIELDS = [
    "component_id",
    "criterion_id",
    "covers",
    "criterion_text",
    "requirement_text",
    "interface",
    "glossary",
    "dependency_interfaces",
]

FORBIDDEN_FIELDS = [
    "spec",
    "constraints",
    "hint_code",
    "spec_bundle_hash",
    "dependency_context",
    "dependency_usage",
    "vars",
]

GEN_MARKER = "pelicangenmarker"
CONSTRAINTS_MARKER = "quokka"
OTHER_REQ_MARKER = "triple"


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _field_names(value):
    if isinstance(value, dict):
        return list(value.keys())
    if dataclasses.is_dataclass(value):
        return [f.name for f in dataclasses.fields(value)]
    return [k for k in vars(value).keys() if not k.startswith("_")]


def _all_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(str(k) + "\n" + _all_text(v) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_all_text(v) for v in value)
    return str(value)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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


def _build_corpus(repo_root: Path) -> None:
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
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** — `triple(x)` MUST return `3 * x`.\n",
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
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 5\n"
        "When triple(x) is called\n"
        "Then it returns 15\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None beyond the quokka ceiling.\n",
    )
    _write(
        repo_root / "legacy" / "foo" / "foo.py",
        "def foo(x):\n"
        "    return 2 * x\n",
    )
    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "# pelicangenmarker\n"
        "def foo(x):\n"
        "    return 2 * x  # pelicangenmarker\n",
    )
    _write(
        repo_root / "gen" / "foo" / "NOTES.md",
        "pelicangenmarker generated notes\n",
    )


def test_ac_assemble_009_criterion_bundle_is_narrow(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )
    assert bundle is not None

    # Identity fields
    assert _get(bundle, "component_id") == "comp-foo"
    assert _get(bundle, "criterion_id") == "AC-FOO-001"
    assert _get(bundle, "covers") == "R-FOO-001"

    # The criterion's own text
    criterion_text = _get(bundle, "criterion_text")
    assert isinstance(criterion_text, str)
    assert "Given x = 2" in criterion_text
    assert "When foo(x) is called" in criterion_text
    assert "Then it returns 4" in criterion_text

    # Its covered requirement's text
    requirement_text = _get(bundle, "requirement_text")
    assert isinstance(requirement_text, str)
    assert "R-FOO-001" in requirement_text
    assert "`foo(x)` MUST return `2 * x`" in requirement_text

    # The interface
    interface = _get(bundle, "interface")
    assert isinstance(interface, str)
    assert "foo(x: int) -> int" in interface

    # The glossary
    glossary = _get(bundle, "glossary")
    assert isinstance(glossary, str)
    assert "a test term" in glossary

    # No dependencies declared, so no dependency interfaces
    dep_ifaces = _get(bundle, "dependency_interfaces")
    assert not dep_ifaces

    # No field derived from gen/, other requirements, or constraints.md
    names = _field_names(bundle)
    for forbidden in FORBIDDEN_FIELDS:
        assert forbidden not in names, (
            f"CriterionBundle unexpectedly has field {forbidden!r}"
        )
    for name in names:
        assert name in EXPECTED_FIELDS, (
            f"CriterionBundle has unexpected field {name!r}"
        )

    everything = "\n".join(_all_text(_get(bundle, name)) for name in names)
    assert GEN_MARKER not in everything, (
        "CriterionBundle contains content derived from gen/<component>/"
    )
    assert CONSTRAINTS_MARKER not in everything, (
        "CriterionBundle contains content derived from constraints.md"
    )
    assert OTHER_REQ_MARKER not in everything, (
        "CriterionBundle contains content from another requirement/criterion"
    )
    assert "R-FOO-002" not in everything
    assert "AC-FOO-002" not in everything
    assert "3 * x" not in everything