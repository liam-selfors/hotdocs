# hotdocs-criterion: sha256:2b477447152d73d78c2c319acc372e99a5fbbd20e4a253b6b6eeec0725988c50
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import spec_reviewer


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

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Foo** \u2014 a test term.\n"
)

REQ_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"
)

AC_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called with `--fast`\n"
    "Then it returns 4\n"
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    _write(specs / "glossary.md", GLOSSARY_MD)
    comp = specs / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQ_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_MD)
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


def _find_spec_linter_path():
    candidates = []
    module_file = Path(spec_reviewer.__file__).resolve()
    for p in module_file.parents:
        if p.name == "gen":
            candidates.append(p / "spec-linter")
        candidates.append(p / "gen" / "spec-linter")
    cwd = Path.cwd().resolve()
    for p in [cwd] + list(cwd.parents):
        candidates.append(p / "gen" / "spec-linter")
    for base in candidates:
        found = _linter_path_in(base)
        if found is not None:
            return found
    return None


def _load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _build_corpus(root)
    linter_path = _find_spec_linter_path()
    if linter_path is not None:
        spec_linter = _load_module(linter_path, "spec_linter")
        assert spec_linter.lint(None, root).hard_failures == 0
    return root


def test_json_format_reports_one_invisible_fast_finding(repo_root, capsys):
    code = spec_reviewer.main(["comp-foo", "--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    findings = field(data, "findings")
    assert len(findings) == 1
    assert field(findings[0], "token") == "--fast"


def test_strict_text_returns_1_with_summary_line(repo_root, capsys):
    code = spec_reviewer.main(["comp-foo", "--strict", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out
    assert code == 1
    lines = [ln for ln in out.splitlines() if ln.strip() != ""]
    assert lines, "expected output on stdout"
    assert lines[-1] == "1 criteria checked, 1 findings, 0 gaps"


@pytest.mark.parametrize(
    "argv_kind",
    ["unknown_target", "bogus_format", "model_without_value", "empty"],
)
def test_usage_errors_return_2(repo_root, capsys, monkeypatch, argv_kind):
    monkeypatch.chdir(repo_root)
    if argv_kind == "unknown_target":
        argv = ["AC-FOO-404", "--repo-root=" + str(repo_root)]
    elif argv_kind == "bogus_format":
        argv = ["comp-foo", "--format=bogus"]
    elif argv_kind == "model_without_value":
        argv = ["comp-foo", "--model"]
    else:
        argv = []
    code = spec_reviewer.main(argv)
    captured = capsys.readouterr()
    assert code == 2
    err_lines = captured.err.splitlines()
    assert err_lines, "expected a usage error on stderr"
    assert err_lines[0].startswith("usage error: ")
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out