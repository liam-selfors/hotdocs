"""AC-VERIFY-013 (Covers: R-VERIFY-012).

Given a compiled criterion whose compiled assertion checks result.foo
  equals 5, and the generated code under test returns 3
When verify_component runs
Then that criterion's result is fail, its failure_detail.expected is 5,
  and its failure_detail.actual is 3
"""

import verifier_orchestrator

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = """# Glossary

- **Foo** — a test term.
"""

PRODUCT = """---
id: P-GAUGE
title: Gauge capability
status: draft
owners: [team-a]
---

# Gauge capability

## Purpose

Report a gauge reading.

## Scope

- In scope: reporting a reading.
- Out of scope: everything else.

## Capability scenarios

### CS-GAUGE-001

Covers: P-GAUGE
Kind: compiled

```gherkin
Given a sample is 7
When read_level is invoked with sample
Then foo equals 5
```
"""

COMPONENT = """---
id: comp-gauge
title: Gauge
status: draft
owners: [team-a]
realizes: [P-GAUGE]
depends_on: []
---

# Gauge

## Purpose

Gauge reports a reading.

## Scope

- In scope: reporting a reading.
- Out of scope: everything else.

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

REQUIREMENT = """# R-GAUGE-001

**R-GAUGE-001** — `read_level(x)` MUST return an object whose `foo` field is `5`.
"""

ACCEPTANCE = """# AC-GAUGE-001

Covers: R-GAUGE-001
Kind: compiled

```gherkin
Given a sample is 7
When read_level is invoked with sample
Then foo equals 5
```
"""

LIBRARY = """# Library

```
read_level(x: int) -> object
```
"""

CONSTRAINTS = """# Constraints

None.
"""

GENERATED_CODE = """from types import SimpleNamespace


def read_level(x):
    return SimpleNamespace(foo=3)
"""


def _build_fixture(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "gauge.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "gauge"
    _write(comp / "component.md", COMPONENT)
    _write(comp / "requirements" / "R-GAUGE-001.md", REQUIREMENT)
    _write(comp / "acceptance" / "AC-GAUGE-001.md", ACCEPTANCE)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(repo_root / "gen" / "gauge" / "gauge.py", GENERATED_CODE)


def test_compiled_failure_carries_typed_expected_and_actual(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = verifier_orchestrator.verify("comp-gauge", repo_root)

    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == "AC-GAUGE-001"]
    assert len(matches) == 1, f"criterion AC-GAUGE-001 not found in {criteria!r}"
    criterion = matches[0]

    assert field(criterion, "result") == "fail", f"unexpected criterion entry: {criterion!r}"

    failure_detail = field(criterion, "failure_detail")
    assert failure_detail is not None, f"missing failure_detail: {criterion!r}"

    expected = field(failure_detail, "expected")
    actual = field(failure_detail, "actual")

    # Values must be their original Python type (ints), not pytest's rendered text.
    assert expected == 5, f"failure_detail.expected was {expected!r}"
    assert isinstance(expected, int) and not isinstance(expected, bool), (
        f"failure_detail.expected has type {type(expected).__name__}"
    )
    assert actual == 3, f"failure_detail.actual was {actual!r}"
    assert isinstance(actual, int) and not isinstance(actual, bool), (
        f"failure_detail.actual has type {type(actual).__name__}"
    )