# hotdocs-criterion: sha256:90070d28cc670f3abd3d9bea156c71172e31e92b26adaea017b652b421baec34
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
    )
    comp = specs / "components" / "foo"
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


def _load_tool_linter():
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
    return load_module(path, "spec_linter")


def test_ac_assemble_017_falls_back_to_tool_root_without_gen(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    assert not (repo_root / "gen").exists()

    spec_linter = _load_tool_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0
    assert not (repo_root / "gen").exists()

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    assert field(bundle, "component_id") == "comp-foo"
    assert "Foo doubles a number." in field(bundle, "spec")
    assert "R-FOO-001" in field(bundle, "spec")
    assert "foo(x: int) -> int" in field(bundle, "interface")
    assert "a test term" in field(bundle, "glossary")
    assert str(field(bundle, "spec_bundle_hash")).startswith("sha256:")

    crit = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )
    assert field(crit, "component_id") == "comp-foo"
    assert field(crit, "criterion_id") == "AC-FOO-001"
    assert field(crit, "covers") == "R-FOO-001"
    assert "Then it returns 4" in field(crit, "criterion_text")
    assert "MUST return `2 * x`" in field(crit, "requirement_text")
    assert "foo(x: int) -> int" in field(crit, "interface")
    assert "a test term" in field(crit, "glossary")

    assert not (repo_root / "gen").exists()