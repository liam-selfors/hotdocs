# hotdocs-criterion: sha256:5f807c7bd21bd5cab45f5281484fb23377235cff1a09318f82aa2ef49a7942d9
import importlib.util
import os
import sys
from pathlib import Path

import pytest

import spec_reviewer


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


GLOSSARY = (
    "# Glossary\n"
    "\n"
    "- **Foo** \u2014 a test term.\n"
)

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

R_FOO_001 = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"
)

R_FOO_002 = (
    "# R-FOO-002\n"
    "\n"
    "**R-FOO-002** \u2014 `foo(x)` MUST return `0` for `x = 0`.\n"
)

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
    "Given x = 0\n"
    "When foo(x) is called\n"
    "Then it returns 0\n"
    "```\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "foo(x: int) -> int\n"
    "```\n"
)

CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "None.\n"
)


def _build_corpus(repo_root):
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


def _linter_path_in(base):
    flat = base / "spec_linter.py"
    if flat.is_file():
        return flat
    pkg = base / "spec_linter" / "__init__.py"
    if pkg.is_file():
        return pkg
    return None


def _find_spec_linter():
    module_file = Path(spec_reviewer.__file__).resolve()
    candidates = []
    for p in module_file.parents:
        if p.name == "gen":
            candidates.append(p / "spec-linter")
    for p in module_file.parents:
        candidates.append(p / "gen" / "spec-linter")
    cwd = Path(os.getcwd()).resolve()
    for p in [cwd] + list(cwd.parents):
        candidates.append(p / "gen" / "spec-linter")
    for base in candidates:
        found = _linter_path_in(base)
        if found is not None:
            return found
    return None


def _assert_lint_clean(repo_root):
    path = _find_spec_linter()
    if path is None:
        # No locatable spec-linter copy; check() lints the corpus itself.
        return
    spec_linter = load_module(path, "spec_linter")
    assert spec_linter.lint(None, repo_root).hard_failures == 0


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _build_corpus(root)
    _assert_lint_clean(root)
    return root


def test_component_and_criterion_targets_resolve_to_sorted_union(repo_root):
    report = spec_reviewer.check(["comp-foo", "AC-FOO-001"], repo_root)
    assert list(field(report, "criteria_checked")) == ["AC-FOO-001", "AC-FOO-002"]


def test_unknown_criterion_id_raises_value_error(repo_root):
    with pytest.raises(ValueError):
        spec_reviewer.check(["AC-FOO-009"], repo_root)


def test_unknown_component_id_raises_value_error(repo_root):
    with pytest.raises(ValueError):
        spec_reviewer.check(["comp-nothing"], repo_root)