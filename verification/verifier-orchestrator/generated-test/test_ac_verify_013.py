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
id: P-GIZMO
title: Gizmo capability
status: draft
owners: [team-a]
---

# Gizmo capability

## Purpose

Gizmos compute values from a seed.

## Scope

- In scope: computing a value from a seed.

## Capability scenarios

### CS-GIZMO-001

Covers: P-GIZMO
Kind: llm-judge

```gherkin
Given a gizmo system
When a value is computed
Then the value is reported
```
"""

COMPONENT = """---
id: comp-gizmo
title: Gizmo
status: draft
owners: [team-a]
realizes: [P-GIZMO]
depends_on: []
---

# Gizmo

## Purpose

Gizmo computes a value object from a seed.
"""

REQUIREMENT = """# R-GIZMO-001

**R-GIZMO-001** — `compute_value(seed)` MUST return an object whose `foo` is 5.
"""

ACCEPTANCE = """# AC-GIZMO-001

Covers: R-GIZMO-001
Kind: compiled

```gherkin
Given a seed is 1
When compute_value is invoked with seed
Then foo equals 5
```
"""

LIBRARY = """# Library

```
compute_value(seed: int) -> object
```
"""

CONSTRAINTS = """# Constraints

None.
"""

GENERATED_CODE = """from types import SimpleNamespace


def compute_value(seed):
    return SimpleNamespace(foo=3)
"""


def _build_fixture(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "gizmo.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "gizmo"
    _write(comp / "component.md", COMPONENT)
    _write(comp / "requirements" / "R-GIZMO-001.md", REQUIREMENT)
    _write(comp / "acceptance" / "AC-GIZMO-001.md", ACCEPTANCE)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(repo_root / "gen" / "gizmo" / "gizmo.py", GENERATED_CODE)


def test_compiled_failure_carries_typed_expected_and_actual(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = verifier_orchestrator.verify("comp-gizmo", repo_root)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-GIZMO-001"]
    assert len(matching) == 1, f"criterion AC-GIZMO-001 not found in {criteria!r}"
    criterion = matching[0]

    assert field(criterion, "kind") == "compiled"
    assert field(criterion, "result") == "fail", criterion

    detail = field(criterion, "failure_detail")
    assert detail is not None, criterion

    expected = field(detail, "expected")
    actual = field(detail, "actual")

    assert expected == 5, detail
    assert isinstance(expected, int) and not isinstance(expected, bool), (
        f"expected must be the original int, got {type(expected).__name__}: {expected!r}"
    )

    assert actual == 3, detail
    assert isinstance(actual, int) and not isinstance(actual, bool), (
        f"actual must be the original int, got {type(actual).__name__}: {actual!r}"
    )

    message = field(detail, "message")
    assert isinstance(message, str) and message.strip(), detail