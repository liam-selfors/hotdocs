import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _get(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def _build_corpus(repo_root):
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
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
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
        "Then it returns 4\n"
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
        "None.\n"
    ))

    _write(repo_root / "specs" / "components" / "bar" / "component.md", (
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/bar/\n"
        "depends_on: [comp-foo]\n"
        "---\n"
        "\n"
        "# Bar\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Bar uses Foo to add one.\n"
    ))

    _write(repo_root / "specs" / "components" / "bar" / "requirements" / "R-BAR-001.md", (
        "# R-BAR-001\n"
        "\n"
        "**R-BAR-001** — `bar(x)` MUST return `foo(x) + 1`.\n"
    ))

    _write(repo_root / "specs" / "components" / "bar" / "acceptance" / "AC-BAR-001.md", (
        "# AC-BAR-001\n"
        "\n"
        "Covers: R-BAR-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When bar(x) is called\n"
        "Then it returns 5\n"
        "```\n"
    ))

    _write(repo_root / "specs" / "components" / "bar" / "interface" / "library.md", (
        "# Library\n"
        "\n"
        "```\n"
        "bar(x: int) -> int\n"
        "```\n"
    ))

    _write(repo_root / "specs" / "components" / "bar" / "constraints.md", (
        "# Constraints\n"
        "\n"
        "None.\n"
    ))


def _lint_clean(repo_root):
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


def test_dependency_interfaces_contains_only_dependency_interface_content(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root)
    _lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-bar", "AC-BAR-001", repo_root)

    dep_interfaces = _get(bundle, "dependency_interfaces")
    assert isinstance(dep_interfaces, dict)
    assert "comp-foo" in dep_interfaces

    dep_value = dep_interfaces["comp-foo"]

    assert "foo(x: int) -> int" in dep_value
    assert "# Library" in dep_value

    forbidden_lines = [
        "id: comp-foo",
        "Foo doubles a number.",
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        "# Constraints",
        "None.",
    ]
    for line in forbidden_lines:
        assert line not in dep_value


def test_dependency_interfaces_empty_mapping_when_no_depends_on(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root)
    _lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)

    dep_interfaces = _get(bundle, "dependency_interfaces")
    assert dep_interfaces is not None
    assert dep_interfaces == {}