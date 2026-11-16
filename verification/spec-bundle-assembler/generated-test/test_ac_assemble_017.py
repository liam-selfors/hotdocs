import spec_bundle_assembler

import importlib.util
import sys
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
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

GLOSSARY_MD = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

REQ_MD = "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"

AC_MD = (
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

LIBRARY_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQ_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)


def _tool_gen() -> Path:
    return next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )


def _load_spec_linter():
    base = _tool_gen() / "spec-linter"
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


def test_ac_assemble_017_falls_back_to_tool_root_without_gen(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    # Precondition: a fresh repo_root with no gen/ directory at all.
    assert not (repo_root / "gen").exists()

    # The dependencies exist under the tool root, where the fallback looks.
    tool_gen = _tool_gen()
    assert (tool_gen / "spec-linter").is_dir()
    assert (tool_gen / "graph-query-engine").is_dir()

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0
    assert not (repo_root / "gen").exists()

    # assemble succeeds, linting and reading the corpus via the tool-root deps.
    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    assert bundle is not None
    assert field(bundle, "component_id") == "comp-foo"
    spec_text = field(bundle, "spec")
    assert "Foo doubles a number." in spec_text
    assert "R-FOO-001" in spec_text
    assert "foo(x: int) -> int" in field(bundle, "interface")
    assert "None." in field(bundle, "constraints")
    assert "a test term" in field(bundle, "glossary")
    assert field(bundle, "hint_code") is None
    assert str(field(bundle, "spec_bundle_hash")).startswith("sha256:")

    # assemble_criterion succeeds too.
    cbundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )
    assert cbundle is not None
    assert field(cbundle, "component_id") == "comp-foo"
    assert field(cbundle, "criterion_id") == "AC-FOO-001"
    assert field(cbundle, "covers") == "R-FOO-001"
    assert "MUST return" in field(cbundle, "requirement_text")
    assert "Then it returns 4" in field(cbundle, "criterion_text")
    assert "foo(x: int) -> int" in field(cbundle, "interface")
    assert "a test term" in field(cbundle, "glossary")

    # repo_root/gen still does not exist afterwards.
    assert not (repo_root / "gen").exists()