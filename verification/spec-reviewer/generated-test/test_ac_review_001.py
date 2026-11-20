# hotdocs-criterion: sha256:36de294461df88b0085a9bc84132208faf9e05c731f2aa3e9765233d1c40922d
import importlib.util
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


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** \u2014 a test term.\n",
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
        "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** \u2014 `foo(x)` MUST return `0` for `x = 0`.\n",
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
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 0\n"
        "When foo(x) is called\n"
        "Then it returns 0\n"
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


def _linter_path_in(base):
    flat = base / "spec_linter.py"
    if flat.is_file():
        return flat
    pkg = base / "spec_linter" / "__init__.py"
    if pkg.is_file():
        return pkg
    return None


def _find_spec_linter_path():
    here = Path(spec_reviewer.__file__).resolve()
    candidates = []
    for parent in here.parents:
        if parent.name == "gen":
            candidates.append(parent / "spec-linter")
        candidates.append(parent / "gen" / "spec-linter")
        candidates.append(parent / "spec-linter")
    for entry in sys.path:
        try:
            p = Path(entry).resolve()
        except Exception:
            continue
        candidates.append(p / "gen" / "spec-linter")
        candidates.append(p / "spec-linter")
    for base in candidates:
        found = _linter_path_in(base)
        if found is not None:
            return found
    return None


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _build_corpus(root)
    linter_path = _find_spec_linter_path()
    if linter_path is not None:
        spec_linter = load_module(linter_path, "spec_linter")
        assert spec_linter.lint(None, root).hard_failures == 0
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