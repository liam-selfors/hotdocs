import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def _get(bundle, field):
    if isinstance(bundle, dict):
        return bundle.get(field)
    return getattr(bundle, field, None)


def _write_fixture(repo_root: Path) -> None:
    glossary = (
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n"
    )

    component_md = (
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

    requirement_md = (
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
    )

    acceptance_md = (
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

    interface_library_md = (
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
    )

    constraints_md = (
        "# Constraints\n"
        "\n"
        "None.\n"
    )

    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "glossary.md").write_text(glossary)

    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface").mkdir(parents=True, exist_ok=True)

    (comp_dir / "component.md").write_text(component_md)
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(requirement_md)
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(acceptance_md)
    (comp_dir / "interface" / "library.md").write_text(interface_library_md)
    (comp_dir / "constraints.md").write_text(constraints_md)


def _load_tool_root_spec_linter():
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


def test_assemble_and_assemble_criterion_succeed_without_gen_dir(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write_fixture(repo_root)

    assert not (repo_root / "gen").exists()

    spec_linter = _load_tool_root_spec_linter()
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0

    assert not (repo_root / "gen").exists()

    spec_bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
    assert _get(spec_bundle, "component_id") == "comp-foo"
    assert "foo" in (_get(spec_bundle, "spec") or "").lower()

    criterion_bundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )
    assert _get(criterion_bundle, "component_id") == "comp-foo"
    assert _get(criterion_bundle, "criterion_id") == "AC-FOO-001"
    assert _get(criterion_bundle, "covers") == "R-FOO-001"

    assert not (repo_root / "gen").exists()