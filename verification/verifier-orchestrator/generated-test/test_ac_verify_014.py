"""AC-VERIFY-014 (Covers: R-VERIFY-013).

Two separate repo_root directories declare a component with the same
slug ("widget") but different code. Verifying them one after the other
in the same process must give each call results that reflect its own
repo_root's code. Neither call may reuse a module cached by the other
repo_root's earlier call.
"""

import sys
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY = """# Glossary

- **Widget** — a test term.
"""

CAPABILITY = """---
id: P-WIDGET
title: Widget capability
status: draft
owners: [team-a]
---

# Widget capability

## Purpose

Numbers can be scaled by a fixed factor.

## Scope

- In scope: scaling numbers.
- Out of scope: everything else.

## Capability scenarios

### CS-WIDGET-001

Covers: P-WIDGET
Kind: compiled

```gherkin
Given a n is 2
When double_it is invoked with [n]
Then real equals 4
```
"""

COMPONENT = """---
id: comp-widget
title: Widget
status: draft
owners: [team-a]
depends_on: []
realizes: [P-WIDGET]
---

# Widget

## Purpose

Widget scales a number by a fixed factor.

## Scope

- In scope: doubling and tripling integers.
- Out of scope: anything else.

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

REQ_001 = """# R-WIDGET-001

**R-WIDGET-001** — `double_it(n)` MUST return `2 * n`.
"""

REQ_002 = """# R-WIDGET-002

**R-WIDGET-002** — `triple_it(n)` MUST return `3 * n`.
"""

AC_001 = """# AC-WIDGET-001

Covers: R-WIDGET-001
Kind: compiled

```gherkin
Given a n is 2
When double_it is invoked with [n]
Then real equals 4
```
"""

AC_002 = """# AC-WIDGET-002

Covers: R-WIDGET-002
Kind: compiled

```gherkin
Given a n is 2
When triple_it is invoked with [n]
Then real equals 6
```
"""

LIBRARY = """# Library

```
double_it(n: int) -> int
triple_it(n: int) -> int
```
"""

CONSTRAINTS = """# Constraints

None.
"""

# Repo A: correct code that matches the declared interface exactly.
CODE_A = """def double_it(n: int) -> int:
    return 2 * n


def triple_it(n: int) -> int:
    return 3 * n
"""

# Repo B: same slug, but double_it is wrong and triple_it is missing.
# That is behavioral failure plus interface drift.
CODE_B = """def double_it(n: int) -> int:
    return 2 * n + 1
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(root: Path, code: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "specs" / "glossary.md", GLOSSARY)
    _write(root / "specs" / "product" / "widget.md", CAPABILITY)
    comp = root / "specs" / "components" / "widget"
    _write(comp / "component.md", COMPONENT)
    _write(comp / "requirements" / "R-WIDGET-001.md", REQ_001)
    _write(comp / "requirements" / "R-WIDGET-002.md", REQ_002)
    _write(comp / "acceptance" / "AC-WIDGET-001.md", AC_001)
    _write(comp / "acceptance" / "AC-WIDGET-002.md", AC_002)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(root / "gen" / "widget" / "widget.py", code)
    return root


def _criterion(report, criterion_id):
    for c in field(report, "criteria"):
        if field(c, "id") == criterion_id:
            return c
    raise AssertionError(
        f"criterion {criterion_id} missing from report: {field(report, 'criteria')!r}"
    )


def _assert_report_for_a(report):
    assert field(report, "component_id") == "comp-widget"
    assert field(report, "interface_drift") is False
    c1 = _criterion(report, "AC-WIDGET-001")
    c2 = _criterion(report, "AC-WIDGET-002")
    assert field(c1, "kind") == "compiled"
    assert field(c2, "kind") == "compiled"
    assert field(c1, "result") == "pass"
    assert field(c2, "result") == "pass"


def _assert_report_for_b(report):
    assert field(report, "component_id") == "comp-widget"
    assert field(report, "interface_drift") is True
    c1 = _criterion(report, "AC-WIDGET-001")
    c2 = _criterion(report, "AC-WIDGET-002")
    assert field(c1, "kind") == "compiled"
    assert field(c2, "kind") == "compiled"
    assert field(c1, "result") == "fail"
    assert field(c2, "result") == "fail"


def test_same_slug_in_two_repo_roots_never_shares_cached_modules(tmp_path):
    sys.modules.pop("widget", None)

    repo_a = _build_repo(tmp_path / "repo_a", CODE_A)
    repo_b = _build_repo(tmp_path / "repo_b", CODE_B)

    # First call: repo A, correct code.
    report_a = verifier_orchestrator.verify("comp-widget", repo_a)
    _assert_report_for_a(report_a)

    # Second call, same process, same slug, different repo_root. It must
    # reflect repo B's broken, drifted code, not repo A's cached module.
    report_b = verifier_orchestrator.verify("comp-widget", repo_b)
    _assert_report_for_b(report_b)

    # Third call: back to repo A. It must reflect repo A's code again,
    # not repo B's module from the immediately preceding call.
    report_a_again = verifier_orchestrator.verify("comp-widget", repo_a)
    _assert_report_for_a(report_a_again)