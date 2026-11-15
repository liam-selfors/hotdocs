"""AC-VERIFY-014 (Covers: R-VERIFY-013).

Two separate repo_root directories each declare a component with the same
slug (``gizmo``) but different code. They are verified one after the other
in the same process. Each call's ``interface_drift`` result and its
compiled-criterion results must reflect that call's own repo_root's code.
They must never come from a module cached during the other repo_root's
earlier call.
"""

from pathlib import Path

import pytest

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# ---------------------------------------------------------------------------
# Fixture corpus
# ---------------------------------------------------------------------------

GLOSSARY = """# Glossary

- **Gizmo** — a test term.
"""

CAPABILITY = """---
id: P-GIZMO
title: Gizmo Arithmetic
status: draft
owners: [team-a]
---

# Gizmo Arithmetic

## Purpose

Lets a caller triple and halve numbers.

## Scope

- In scope: tripling and halving integers.
- Out of scope: everything else.

## Capability scenarios

### CS-GIZMO-001

Covers: P-GIZMO
Kind: llm-judge

```gherkin
Given a number is 3
When triple is invoked with [number]
Then value equals 9
```
"""

COMPONENT_MD = """---
id: comp-gizmo
title: Gizmo
status: draft
owners: [team-a]
depends_on: []
realizes: [P-GIZMO]
---

# Gizmo

## Purpose

Gizmo triples and halves numbers.

## Scope

- In scope: tripling and halving integers.
- Out of scope: any other arithmetic.

## Definitions

None.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

- Initial draft.
"""

R_001 = """# R-GIZMO-001

**R-GIZMO-001** — `triple(x)` MUST return a dict whose `value` is `3 * x`.
"""

R_002 = """# R-GIZMO-002

**R-GIZMO-002** — `halve(x)` MUST return a dict whose `value` is `x // 2`.
"""

AC_001 = """# AC-GIZMO-001

Covers: R-GIZMO-001
Kind: compiled

```gherkin
Given a number is 3
When triple is invoked with [number]
Then value equals 9
```
"""

AC_002 = """# AC-GIZMO-002

Covers: R-GIZMO-002
Kind: compiled

```gherkin
Given a number is 8
When halve is invoked with [number]
Then value equals 4
```
"""

LIBRARY_MD = """# Library

```
triple(x: int) -> dict
halve(x: int) -> dict
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""

# Code that matches the interface and satisfies both criteria.
GOOD_CODE = '''class _Result(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def triple(x: int) -> dict:
    return _Result(value=3 * x)


def halve(x: int) -> dict:
    return _Result(value=x // 2)
'''

# Same slug and module name, but different code. `triple` returns the wrong
# value and the declared `halve` is missing entirely, so the code has
# interface drift.
BAD_CODE = '''class _Result(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def triple(x: int) -> dict:
    return _Result(value=3 * x + 1)
'''


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_repo(root: Path, code: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "specs" / "glossary.md", GLOSSARY)
    _write(root / "specs" / "product" / "P-GIZMO.md", CAPABILITY)
    comp = root / "specs" / "components" / "gizmo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-GIZMO-001.md", R_001)
    _write(comp / "requirements" / "R-GIZMO-002.md", R_002)
    _write(comp / "acceptance" / "AC-GIZMO-001.md", AC_001)
    _write(comp / "acceptance" / "AC-GIZMO-002.md", AC_002)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(root / "gen" / "gizmo" / "gizmo.py", code)
    return root


def _criterion_results(report) -> dict:
    out = {}
    for c in field(report, "criteria"):
        out[field(c, "id")] = field(c, "result")
    return out


def _assert_good(report, label):
    assert field(report, "interface_drift") is False, (
        f"{label}: repo with matching code reported interface drift "
        f"(stale module from the other repo_root?)"
    )
    results = _criterion_results(report)
    assert results.get("AC-GIZMO-001") == "pass", (label, results)
    assert results.get("AC-GIZMO-002") == "pass", (label, results)


def _assert_bad(report, label):
    assert field(report, "interface_drift") is True, (
        f"{label}: repo whose code lacks declared `halve` reported no "
        f"interface drift (stale module from the other repo_root?)"
    )
    results = _criterion_results(report)
    assert "AC-GIZMO-001" in results, (label, results)
    assert "AC-GIZMO-002" in results, (label, results)
    assert results["AC-GIZMO-001"] != "pass", (label, results)
    assert results["AC-GIZMO-002"] != "pass", (label, results)


@pytest.mark.parametrize("order", ["good_then_bad", "bad_then_good"])
def test_same_slug_across_repo_roots_never_reuses_cached_module(tmp_path, order):
    good_root = _make_repo(tmp_path / "repo_good", GOOD_CODE)
    bad_root = _make_repo(tmp_path / "repo_bad", BAD_CODE)
    assert good_root != bad_root

    if order == "good_then_bad":
        first = verifier_orchestrator.verify("comp-gizmo", good_root)
        _assert_good(first, "first call (good repo)")
        second = verifier_orchestrator.verify("comp-gizmo", bad_root)
        _assert_bad(second, "second call (bad repo)")
    else:
        first = verifier_orchestrator.verify("comp-gizmo", bad_root)
        _assert_bad(first, "first call (bad repo)")
        second = verifier_orchestrator.verify("comp-gizmo", good_root)
        _assert_good(second, "second call (good repo)")