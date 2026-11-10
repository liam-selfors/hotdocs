import sys
import importlib.util
from pathlib import Path

import spec_bundle_assembler


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _lint_clean(repo_root: Path) -> None:
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", (
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n"
    ))

    _write(repo_root / "specs" / "components" / "foo" / "component.md", (
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
    ))

    _write(repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md", (
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`. MARKER_R001_ONLY\n"
    ))
    _write(repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-002.md", (
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** — `foo(x)` MUST accept only integers. MARKER_R002_ONLY\n"
    ))
    _write(repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-003.md", (
        "# R-FOO-003\n"
        "\n"
        "**R-FOO-003** — `foo(x)` MUST never raise for valid input. MARKER_R003_ONLY\n"
    ))

    _write(repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md", (
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4 MARKER_AC001_ONLY\n"
        "```\n"
    ))
    _write(repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-002.md", (
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = \"not an int\"\n"
        "When foo(x) is called\n"
        "Then it rejects the input MARKER_AC002_ONLY\n"
        "```\n"
    ))
    _write(repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-003.md", (
        "# AC-FOO-003\n"
        "\n"
        "Covers: R-FOO-003\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 5\n"
        "When foo(x) is called\n"
        "Then it does not raise MARKER_AC003_ONLY\n"
        "```\n"
    ))

    _write(repo_root / "specs" / "components" / "foo" / "interface" / "library.md", (
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
    ))

    _write(repo_root / "specs" / "components" / "foo" / "constraints.md", (
        "# Constraints\n"
        "\n"
        "CONSTRAINTS_MARKER_TEXT_UNIQUE should never appear in a CriterionBundle.\n"
    ))

    _write(repo_root / "legacy" / "foo" / "foo.py", (
        "def foo(x):\n"
        "    return x * 2\n"
    ))

    _write(repo_root / "gen" / "foo" / "foo.py", (
        "GEN_MARKER_CONTENT = 'should never appear in a CriterionBundle'\n"
        "\n"
        "\n"
        "def foo(x):\n"
        "    return x * 2\n"
    ))


def test_assemble_criterion_scopes_to_one_criterion_and_its_requirement(tmp_path):
    repo_root = tmp_path
    _build_corpus(repo_root)
    _lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-002", repo_root)

    component_id = _field(bundle, "component_id")
    criterion_id = _field(bundle, "criterion_id")
    covers = _field(bundle, "covers")
    criterion_text = _field(bundle, "criterion_text")
    requirement_text = _field(bundle, "requirement_text")
    interface = _field(bundle, "interface")
    glossary = _field(bundle, "glossary")
    dependency_interfaces = _field(bundle, "dependency_interfaces")

    assert component_id == "comp-foo"
    assert criterion_id == "AC-FOO-002"
    assert covers == "R-FOO-002"

    assert "MARKER_AC002_ONLY" in criterion_text
    assert "MARKER_AC001_ONLY" not in criterion_text
    assert "MARKER_AC003_ONLY" not in criterion_text

    assert "MARKER_R002_ONLY" in requirement_text
    assert "MARKER_R001_ONLY" not in requirement_text
    assert "MARKER_R003_ONLY" not in requirement_text

    assert "foo(x: int) -> int" in interface

    assert "Foo" in glossary
    assert "a test term" in glossary

    assert dependency_interfaces == {}

    combined = "\n".join([
        str(component_id),
        str(criterion_id),
        str(covers),
        str(criterion_text),
        str(requirement_text),
        str(interface),
        str(glossary),
        str(dependency_interfaces),
    ])

    assert "GEN_MARKER_CONTENT" not in combined
    assert "should never appear" not in combined
    assert "CONSTRAINTS_MARKER_TEXT_UNIQUE" not in combined
    assert "MARKER_R001_ONLY" not in combined
    assert "MARKER_R003_ONLY" not in combined
    assert "MARKER_AC001_ONLY" not in combined
    assert "MARKER_AC003_ONLY" not in combined