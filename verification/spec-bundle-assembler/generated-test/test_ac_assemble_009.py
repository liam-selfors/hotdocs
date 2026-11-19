# hotdocs-criterion: sha256:789eb94480b782ec42f46955936b4108caad180ab672d5173b4f43c9aadb8c35
import dataclasses
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


GEN_MARKER = "genmarkerzzq"
OTHER_REQ_MARKER = "triple_quuxzz"
CONSTRAINT_MARKER = "zorbleconstraintqv"
OTHER_AC_MARKER = "otheracmarkerwv"

ALLOWED_FIELDS = {
    "component_id",
    "criterion_id",
    "covers",
    "criterion_text",
    "requirement_text",
    "interface",
    "glossary",
    "dependency_interfaces",
    "testing",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def field_names(value):
    if isinstance(value, dict):
        return list(value.keys())
    if dataclasses.is_dataclass(value):
        return [f.name for f in dataclasses.fields(value)]
    return list(value.keys())


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


def build_corpus(repo_root):
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
        "**R-FOO-002** — `" + OTHER_REQ_MARKER + "(x)` MUST return `3 * x`.\n",
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
        "Given x = 5 and " + OTHER_AC_MARKER + "\n"
        "When " + OTHER_REQ_MARKER + "(x) is called\n"
        "Then it returns 15\n"
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
        "None. " + CONSTRAINT_MARKER + ".\n",
    )
    write(
        repo_root / "legacy" / "foo" / "foo.py",
        "def foo(x):\n"
        "    return 2 * x\n",
    )
    write(
        repo_root / "gen" / "foo" / "foo.py",
        "def foo(x):\n"
        "    return 2 * x  # " + GEN_MARKER + "\n",
    )


def test_criterion_bundle_contains_only_narrow_content(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)

    # Positive content
    assert field(bundle, "component_id") == "comp-foo"
    assert field(bundle, "criterion_id") == "AC-FOO-001"
    assert field(bundle, "covers") == "R-FOO-001"
    assert "Then it returns 4" in field(bundle, "criterion_text")
    assert "Given x = 2" in field(bundle, "criterion_text")
    assert "`foo(x)` MUST return `2 * x`" in field(bundle, "requirement_text")
    assert "foo(x: int) -> int" in field(bundle, "interface")
    assert "a test term" in field(bundle, "glossary")

    # No field outside the documented CriterionBundle schema
    names = field_names(bundle)
    assert set(names) <= ALLOWED_FIELDS, names
    for forbidden in ("constraints", "hint_code", "spec", "spec_bundle_hash", "code"):
        assert forbidden not in names

    # No content derived from gen/foo/, other requirements, or constraints.md
    for name in names:
        rendered = repr(field(bundle, name))
        assert GEN_MARKER not in rendered, name
        assert OTHER_REQ_MARKER not in rendered, name
        assert "R-FOO-002" not in rendered, name
        assert CONSTRAINT_MARKER not in rendered, name
        assert "# Constraints" not in rendered, name
        assert OTHER_AC_MARKER not in rendered, name