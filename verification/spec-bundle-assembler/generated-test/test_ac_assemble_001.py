import spec_bundle_assembler

import dataclasses
import importlib.util
import sys
from pathlib import Path


SCHEMA_FIELDS = [
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

ACCEPTANCE_MARKERS = [
    "AC-FOO-001",
    "Given x = 2",
    "When foo(x) is called",
    "Then it returns 4",
    "Kind: generated-test",
    "gherkin",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
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


def _field_names(bundle):
    if isinstance(bundle, dict):
        return list(bundle.keys())
    if dataclasses.is_dataclass(bundle):
        return [f.name for f in dataclasses.fields(bundle)]
    return [n for n in SCHEMA_FIELDS if hasattr(bundle, n)]


def _collect_strings(value, out):
    if value is None:
        return
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            _collect_strings(k, out)
            _collect_strings(v, out)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            _collect_strings(v, out)
    else:
        out.append(str(value))


def test_ac_assemble_001_cold_bundle_has_spec_interface_constraints_and_no_acceptance(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    assert field(bundle, "component_id") == "comp-foo"

    # Spec content: component.md body + requirements/ content.
    spec_text = field(bundle, "spec")
    assert isinstance(spec_text, str)
    assert "Foo doubles a number." in spec_text
    assert "`foo(x)` MUST return `2 * x`." in spec_text

    # Interface content.
    interface_text = field(bundle, "interface")
    assert isinstance(interface_text, str)
    assert "foo(x: int) -> int" in interface_text

    # Constraints content.
    constraints_text = field(bundle, "constraints")
    assert isinstance(constraints_text, str)
    assert "None." in constraints_text

    # Cold mode: no hint code.
    assert field(bundle, "hint_code") is None

    # No field derived from acceptance/: no field named after acceptance.
    names = _field_names(bundle)
    for name in names:
        lowered = name.lower()
        assert "acceptance" not in lowered, name
        assert "criteri" not in lowered, name

    # And no acceptance-derived content anywhere in the bundle.
    strings = []
    for name in set(names) | {n for n in SCHEMA_FIELDS if n in names}:
        _collect_strings(field(bundle, name), strings)
    combined = "\n".join(strings)
    for marker in ACCEPTANCE_MARKERS:
        assert marker not in combined, (
            f"acceptance-derived text {marker!r} found in bundle"
        )