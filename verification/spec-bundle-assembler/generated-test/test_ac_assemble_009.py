# hotdocs-criterion: sha256:5d1ada16d0f4c1af2142ba96fb5a4a305c93cfb69a5dfa48daabaa7cc52cbe62
import dataclasses
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


GEN_MARKER = "zqgenmarkerq"
OTHER_REQ_MARKER = "zqotherreqmarkerq"
CONSTRAINT_MARKER = "zqconstraintmarkerq"

ALLOWED_FIELDS = {
    "component_id",
    "criterion_id",
    "covers",
    "criterion_text",
    "requirement_text",
    "interface",
    "glossary",
    "dependency_interfaces",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
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
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** — `foo(x)` MUST accept negative integers "
        + OTHER_REQ_MARKER
        + ".\n",
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
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = -3\n"
        "When foo(x) is called\n"
        "Then it returns -6\n"
        "```\n",
    )

    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n",
    )

    write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None. " + CONSTRAINT_MARKER + "\n",
    )

    write(
        repo_root / "legacy" / "foo" / "foo.py",
        "def foo(x):\n"
        "    return 2 * x\n",
    )

    # Existing gen/<component>/ content that must never leak into the bundle.
    write(
        repo_root / "gen" / "foo" / "foo.py",
        "# " + GEN_MARKER + "\n"
        "GEN_SENTINEL = " + repr(GEN_MARKER) + "\n"
        "def foo(x):\n"
        "    return 2 * x\n",
    )


def field_names(bundle):
    if dataclasses.is_dataclass(bundle):
        return [f.name for f in dataclasses.fields(bundle)]
    if isinstance(bundle, dict):
        return list(bundle.keys())
    return [n for n in ALLOWED_FIELDS if hasattr(bundle, n)]


def test_criterion_bundle_contains_only_narrow_inputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )

    # Identity fields
    assert field(bundle, "component_id") == "comp-foo"
    assert field(bundle, "criterion_id") == "AC-FOO-001"
    assert field(bundle, "covers") == "R-FOO-001"

    # The criterion's own text
    criterion_text = field(bundle, "criterion_text")
    assert isinstance(criterion_text, str)
    assert "Given x = 2" in criterion_text
    assert "Then it returns 4" in criterion_text

    # The covered requirement's text
    requirement_text = field(bundle, "requirement_text")
    assert isinstance(requirement_text, str)
    assert "MUST return `2 * x`" in requirement_text

    # The interface
    interface = field(bundle, "interface")
    assert isinstance(interface, str)
    assert "foo(x: int) -> int" in interface

    # The glossary
    glossary = field(bundle, "glossary")
    assert isinstance(glossary, str)
    assert "a test term" in glossary

    # No dependencies declared -> empty dependency_interfaces
    assert dict(field(bundle, "dependency_interfaces")) == {}

    # No field beyond the CriterionBundle schema (no constraints, spec,
    # hint_code, or anything else derived from excluded sources).
    names = field_names(bundle)
    assert names, "could not enumerate CriterionBundle fields"
    extra = set(names) - ALLOWED_FIELDS
    assert extra == set(), "unexpected fields: " + repr(sorted(extra))
    for forbidden in ("constraints", "hint_code", "spec", "vars"):
        assert forbidden not in names

    # No field's content derived from gen/<component>/, another
    # requirements/ file, or constraints.md.
    for name in names:
        rendered = repr(field(bundle, name))
        assert GEN_MARKER not in rendered, name + " leaks gen/ content"
        assert OTHER_REQ_MARKER not in rendered, (
            name + " leaks another requirements/ file"
        )
        assert CONSTRAINT_MARKER not in rendered, (
            name + " leaks constraints.md"
        )
        assert "R-FOO-002" not in rendered or name == "criterion_text", (
            name + " references a non-covered requirement"
        )