import importlib.util
import sys
from pathlib import Path

import pytest

import spec_reviewer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

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

R_FOO_001 = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

R_FOO_002 = "# R-FOO-002\n\n**R-FOO-002** — `foo(x)` MUST return an `int`.\n"

AC_FOO_001 = (
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

AC_FOO_002 = (
    "# AC-FOO-002\n"
    "\n"
    "Covers: R-FOO-002\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 3\n"
    "When foo(x) is called\n"
    "Then it returns an int\n"
    "```\n"
)

LIBRARY_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"
    _write(specs / "glossary.md", GLOSSARY)
    comp = specs / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", R_FOO_001)
    _write(comp / "requirements" / "R-FOO-002.md", R_FOO_002)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_FOO_001)
    _write(comp / "acceptance" / "AC-FOO-002.md", AC_FOO_002)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)


def _load_spec_linter():
    gen = next(
        p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _build_corpus(root)
    monkeypatch.chdir(root)
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0
    return root


def test_targets_resolve_to_sorted_deduplicated_criteria(repo_root):
    report = spec_reviewer.check(["comp-foo", "AC-FOO-001"], repo_root)
    assert list(field(report, "criteria_checked")) == ["AC-FOO-001", "AC-FOO-002"]


def test_unknown_criterion_id_raises_value_error(repo_root):
    with pytest.raises(ValueError):
        spec_reviewer.check(["AC-FOO-009"], repo_root)


def test_unknown_component_id_raises_value_error(repo_root):
    with pytest.raises(ValueError):
        spec_reviewer.check(["comp-nothing"], repo_root)