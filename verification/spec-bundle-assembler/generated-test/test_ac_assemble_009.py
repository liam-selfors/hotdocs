import spec_bundle_assembler

import dataclasses
import importlib.util
import sys
from pathlib import Path


GEN_MARKER = "zqgenmarkerx81"
OTHER_REQ_MARKER = "zqotherreqmarkerk3v"
CONSTRAINTS_MARKER = "zqconstraintsmarkerp5w"
MARKERS = (GEN_MARKER, OTHER_REQ_MARKER, CONSTRAINTS_MARKER)

DOCUMENTED_FIELDS = (
    "component_id",
    "criterion_id",
    "covers",
    "criterion_text",
    "requirement_text",
    "interface",
    "glossary",
    "dependency_interfaces",
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
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
    # The "other" requirement: must never leak into the bundle for AC-FOO-002.
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x` ("
        + OTHER_REQ_MARKER
        + ").\n",
    )
    # The covered requirement of the criterion under assembly.
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
        "triple(x: int) -> int\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None. " + CONSTRAINTS_MARKER + "\n",
    )
    # Existing generated content for the component.
    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "# " + GEN_MARKER + "\n"
        "GEN_CONSTANT = '" + GEN_MARKER + "'\n"
        "\n"
        "\n"
        "def foo(x):\n"
        "    return 2 * x\n",
    )
    _write(
        repo_root / "gen" / "foo" / "notes.txt",
        "generated notes " + GEN_MARKER + "\n",
    )


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


def _collect_strings(value, out):
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            _collect_strings(k, out)
            _collect_strings(v, out)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            _collect_strings(v, out)
    elif value is not None:
        out.append(str(value))
    return out


def test_ac_assemble_009_criterion_bundle_is_narrow(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-002", repo_root
    )

    # Identity of the bundle.
    assert field(bundle, "component_id") == "comp-foo"
    assert field(bundle, "criterion_id") == "AC-FOO-002"
    assert field(bundle, "covers") == "R-FOO-002"

    # That criterion's own text.
    criterion_text = field(bundle, "criterion_text")
    assert isinstance(criterion_text, str)
    assert "When triple(x) is called" in criterion_text
    assert "Then it returns 15" in criterion_text
    # Not the other criterion's text.
    assert "Then it returns 4" not in criterion_text

    # Its covered requirement's text.
    requirement_text = field(bundle, "requirement_text")
    assert isinstance(requirement_text, str)
    assert "R-FOO-002" in requirement_text
    assert "MUST return `3 * x`" in requirement_text

    # The interface.
    interface = field(bundle, "interface")
    assert isinstance(interface, str)
    assert "triple(x: int) -> int" in interface
    assert "foo(x: int) -> int" in interface

    # The glossary.
    glossary = field(bundle, "glossary")
    assert isinstance(glossary, str)
    assert "a test term" in glossary

    # No SpecBundle-only fields that would carry excluded content.
    if dataclasses.is_dataclass(bundle):
        names = {f.name for f in dataclasses.fields(bundle)}
    elif isinstance(bundle, dict):
        names = set(bundle.keys())
    else:
        names = set()
    for forbidden in ("spec", "constraints", "hint_code", "spec_bundle_hash"):
        assert forbidden not in names, f"CriterionBundle has forbidden field {forbidden!r}"

    # No field carries content from gen/foo/, any other requirements/ file,
    # or constraints.md.
    strings = []
    for name in DOCUMENTED_FIELDS:
        try:
            value = field(bundle, name)
        except (KeyError, AttributeError):
            continue
        _collect_strings(value, strings)
    if dataclasses.is_dataclass(bundle):
        for f in dataclasses.fields(bundle):
            _collect_strings(getattr(bundle, f.name), strings)
    elif isinstance(bundle, dict):
        _collect_strings(bundle, strings)
    strings.append(repr(bundle))

    for marker in MARKERS:
        for s in strings:
            assert marker not in s, f"CriterionBundle leaked excluded content: {marker}"

    # The other requirement's own statement must not appear either.
    for s in strings:
        assert "MUST return `2 * x`" not in s