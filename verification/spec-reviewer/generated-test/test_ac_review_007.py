import importlib.util
import json
import sys
from pathlib import Path

import pytest

import spec_reviewer


GLOSSARY = """# Glossary

- **Foo** — a test term.
"""

COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: true
source_path: legacy/foo/
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
"""

REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called with `--fast`
Then it returns 4
```
"""

LIBRARY_MD = """# Library

```
foo(x: int) -> int
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
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


def _call_main(argv):
    try:
        return spec_reviewer.main(argv)
    except SystemExit as exc:  # pragma: no cover - contract violation
        pytest.fail(f"main({argv!r}) called sys.exit({exc.code!r}) instead of returning")


@pytest.fixture
def repo_root(tmp_path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    _build_corpus(root)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0, f"fixture is not lint-clean: {report!r}"
    capsys.readouterr()
    return root


def test_json_format_reports_invisible_fast_flag(repo_root, capsys):
    code = _call_main(["comp-foo", "--format=json", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out
    assert code == 0
    doc = json.loads(out)
    findings = doc["findings"]
    assert len(findings) == 1, findings
    assert findings[0]["token"] == "--fast"


def test_strict_text_returns_one_with_summary_line(repo_root, capsys):
    code = _call_main(["comp-foo", "--strict", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out
    assert code == 1
    lines = out.rstrip("\n").splitlines()
    assert lines, "no stdout produced"
    assert lines[-1].strip() == "1 criteria checked, 1 findings, 0 gaps"


@pytest.mark.parametrize(
    "argv_kind",
    ["unknown_target", "bogus_format", "model_without_value", "empty"],
)
def test_usage_errors_return_two(repo_root, capsys, argv_kind):
    argv = {
        "unknown_target": ["AC-FOO-404", f"--repo-root={repo_root}"],
        "bogus_format": ["comp-foo", "--format=bogus"],
        "model_without_value": ["comp-foo", "--model"],
        "empty": [],
    }[argv_kind]
    code = _call_main(argv)
    captured = capsys.readouterr()
    assert code == 2
    err_lines = captured.err.splitlines()
    assert err_lines, "nothing printed to stderr"
    assert err_lines[0].startswith("usage error: "), captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out