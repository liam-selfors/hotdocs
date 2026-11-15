"""AC-VERIFY-021 (Covers: R-VERIFY-018): verifier-orchestrator's main(argv) CLI."""

import json
from pathlib import Path

import pytest

import verifier_orchestrator


GLOSSARY = """# Glossary

- **Foo** — a test term.
"""

PRODUCT = """---
id: P-FOO
title: Foo capability
status: draft
owners: [team-a]
---

# Foo capability

## Purpose

Boxes a doubled number.

## Scope

- In scope: boxing a doubled number.
- Out of scope: everything else.

## Capability scenarios

### CS-FOO-001

Covers: P-FOO
Kind: generated-test

```gherkin
Given the number 3
When it is boxed
Then the box holds 6
```
"""

COMPONENT = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
realizes: [P-FOO]
depends_on: []
---

# Foo

## Purpose

Foo boxes a doubled number.

## Scope

- In scope: boxing a doubled number.
- Out of scope: everything else.

## Definitions

None.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

None.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

- Initial draft.
"""

REQUIREMENT = """# R-FOO-001

**R-FOO-001** — `make_box(n)` MUST return an object whose `value` is `2 * n`.
"""

ACCEPTANCE = """# AC-FOO-001

Covers: R-FOO-001
Kind: compiled

```gherkin
Given a number is 3
When make_box is invoked with [number]
Then value equals 6
```
"""

LIBRARY = """# Library

```
make_box(n: int) -> object
```
"""

CONSTRAINTS = """# Constraints

None.
"""

PASSING_CODE = '''"""Foo boxes a doubled number."""

import types as _types


def make_box(n: int) -> object:
    """Return an object whose value is 2 * n."""
    return _types.SimpleNamespace(value=2 * n)
'''

FAILING_CODE = '''"""Foo boxes a doubled number."""

import types as _types


def make_box(n: int) -> object:
    """Return an object whose value is 2 * n."""
    return _types.SimpleNamespace(value=n + 1)
'''


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(root: Path, code: str) -> Path:
    _write(root / "specs" / "glossary.md", GLOSSARY)
    _write(root / "specs" / "product" / "foo.md", PRODUCT)
    comp = root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(root / "gen" / "foo" / "foo.py", code)
    return root


def _field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _run(argv):
    try:
        return verifier_orchestrator.main(argv)
    except SystemExit as exc:  # tolerate a usage path that exits with the code
        code = exc.code
        return code if isinstance(code, int) else (0 if code is None else 2)


@pytest.fixture
def passing_root(tmp_path, monkeypatch):
    root = _build_repo(tmp_path / "pass_repo", PASSING_CODE)
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    return root


@pytest.fixture
def failing_root(tmp_path, monkeypatch):
    root = _build_repo(tmp_path / "fail_repo", FAILING_CODE)
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    return root


def test_json_equals_form_passes(passing_root, capsys):
    capsys.readouterr()
    code = _run(["comp-foo", f"--repo-root={passing_root}", "--format=json"])
    out = capsys.readouterr().out
    assert code == 0, out
    report = json.loads(out.strip())
    assert _field(report, "overall") == "pass"


def test_text_separate_form_passes(passing_root, capsys):
    capsys.readouterr()
    code = _run(["comp-foo", "--repo-root", str(passing_root), "--format", "text"])
    out = capsys.readouterr().out
    assert code == 0, out
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines, out
    assert lines[0] == "comp-foo: pass"
    criterion_lines = lines[1:]
    assert criterion_lines, out
    for line in criterion_lines:
        assert line[:1].isspace(), f"criterion line not indented: {line!r}"
    assert any(line.strip() == "AC-FOO-001: pass" for line in criterion_lines), out


def test_failing_criterion_returns_1(failing_root, capsys):
    capsys.readouterr()
    code = _run(["comp-foo", f"--repo-root={failing_root}"])
    out = capsys.readouterr().out
    assert code == 1, out


@pytest.mark.parametrize(
    "case",
    ["no-args", "bogus-format", "unknown-arg", "repo-root-last", "no-component"],
)
def test_usage_errors_return_2(passing_root, capsys, case):
    argvs = {
        "no-args": [],
        "bogus-format": ["comp-foo", f"--repo-root={passing_root}", "--format=bogus"],
        "unknown-arg": ["comp-foo", f"--repo-root={passing_root}", "--bogus-flag"],
        "repo-root-last": ["comp-foo", "--repo-root"],
        "no-component": ["comp-nope", f"--repo-root={passing_root}"],
    }
    capsys.readouterr()
    code = _run(argvs[case])
    captured = capsys.readouterr()
    assert code == 2, (case, captured.out, captured.err)
    assert "hotdocs verify-component" in captured.err, (case, captured.err)