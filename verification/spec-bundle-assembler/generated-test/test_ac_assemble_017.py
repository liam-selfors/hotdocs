import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _tool_gen_dir():
    return next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )


def _module_path(base, module_name):
    flat = base / (module_name + ".py")
    if flat.is_file():
        return flat
    return base / module_name / "__init__.py"


def _load_tool_spec_linter():
    gen = _tool_gen_dir()
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


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
    )
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
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
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
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
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )
    _write(
        repo_root / "legacy" / "foo" / "foo.py",
        "def foo(x):\n"
        "    return 2 * x\n",
    )


def test_ac_assemble_017_tool_root_fallback_without_repo_gen(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    assert not (repo_root / "gen").exists()

    tool_gen = _tool_gen_dir()
    # The tool root's gen directory is not inside the fixture repo.
    assert repo_root.resolve() not in tool_gen.resolve().parents
    assert tool_gen.resolve() != (repo_root / "gen").resolve()

    # The two dependencies are present under the tool root.
    linter_path = _module_path(tool_gen / "spec-linter", "spec_linter")
    gqe_path = _module_path(tool_gen / "graph-query-engine", "graph_query_engine")
    assert linter_path.is_file()
    assert gqe_path.is_file()

    spec_linter = _load_tool_spec_linter()
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0

    # Linting the fixture must not have created repo_root/gen.
    assert not (repo_root / "gen").exists()

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    assert bundle is not None
    assert _field(bundle, "component_id") == "comp-foo"
    spec_text = _field(bundle, "spec") or ""
    assert "R-FOO-001" in spec_text
    assert "Foo doubles a number." in spec_text
    interface_text = _field(bundle, "interface") or ""
    assert "foo(x: int) -> int" in interface_text
    glossary_text = _field(bundle, "glossary") or ""
    assert "a test term" in glossary_text
    assert _field(bundle, "hint_code") is None

    assert not (repo_root / "gen").exists()

    crit = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )
    assert crit is not None
    assert _field(crit, "component_id") == "comp-foo"
    assert _field(crit, "criterion_id") == "AC-FOO-001"
    assert _field(crit, "covers") == "R-FOO-001"
    criterion_text = _field(crit, "criterion_text") or ""
    assert "foo(x) is called" in criterion_text
    requirement_text = _field(crit, "requirement_text") or ""
    assert "2 * x" in requirement_text
    crit_interface = _field(crit, "interface") or ""
    assert "foo(x: int) -> int" in crit_interface

    assert not (repo_root / "gen").exists()