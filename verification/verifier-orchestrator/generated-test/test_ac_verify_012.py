import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY = """# Glossary

- **Widget** — a test term.
"""

PRODUCT = """---
id: P-WIDGET
title: Widget Capability
status: draft
owners: [team-a]
---

# Widget Capability

## Purpose

Widgets double numbers.

## Scope

- In scope: doubling.
- Out of scope: everything else.

## Capability scenarios

### CS-WIDGET-001

Covers: P-WIDGET
Kind: llm-judge

```gherkin
Given a number to double
When the widget doubles it
Then the result is twice the number
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

Widget doubles a number.

## Scope

- In scope: doubling a number.
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

REQUIREMENT = """# R-WIDGET-001

**R-WIDGET-001** — `double_it(x)` MUST return `2 * x`.
"""

ACCEPTANCE = """# AC-WIDGET-001

Covers: R-WIDGET-001
Kind: llm-judge

```gherkin
Given the widget specification text
When a reviewer reads the doubling requirement
Then the requirement is clear and free of contradiction
```
"""

LIBRARY = """# Library

```
double_it(x: int) -> int
```
"""

CONSTRAINTS = """# Constraints

None.
"""

GEN_CODE = """def double_it(x):
    return 2 * x
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "widget.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "widget"
    _write(comp / "component.md", COMPONENT)
    _write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT)
    _write(comp / "acceptance" / "AC-WIDGET-001.md", ACCEPTANCE)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(repo_root / "gen" / "widget" / "widget.py", GEN_CODE)


def _criterion_id_of(bundle):
    try:
        return bundle["criterion_id"]
    except Exception:
        return getattr(bundle, "criterion_id", None)


def test_ac_verify_012_llm_judge_called_exactly_once(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    log_path = tmp_path / "judge_calls.log"

    def judge(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"criterion_id": _criterion_id_of(bundle)}) + "\n")
        return {"result": "pass", "rationale": "The requirement is clear."}

    report = verifier_orchestrator.verify("comp-widget", repo_root, judge=judge)

    calls = []
    if log_path.exists():
        calls = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    # Never zero times (judge was configured), never more than once.
    assert len(calls) == 1, f"judge called {len(calls)} times, expected exactly 1"

    recorded_id = calls[0]["criterion_id"]
    if recorded_id is not None:
        assert recorded_id == "AC-WIDGET-001"

    criteria = field(report, "criteria")
    entries = [c for c in criteria if field(c, "id") == "AC-WIDGET-001"]
    assert len(entries) == 1
    assert field(entries[0], "kind") == "llm-judge"
    assert field(entries[0], "result") != "skipped"