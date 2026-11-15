"""AC-VERIFY-005 (Covers: R-VERIFY-005).

Given a component where every compiled and generated-test criterion passes,
its tests kill every mutant (mutation_score 1.0), interface_drift is false,
and the only llm-judge criterion is skipped
When verify runs
Then the overall verdict is pass: a skipped finding alone never causes fail.
"""

import verifier_orchestrator

import json
from pathlib import Path


COMPONENT_ID = "comp-gizmo"
SLUG = "gizmo"
MODULE = "gizmo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


GLOSSARY = """# Glossary

- **Gizmo** — a component that doubles numbers.
"""

CAPABILITY = """---
id: P-GIZMO
title: Gizmo Doubling
status: draft
owners: [team-a]
---

# Gizmo Doubling

## Purpose

Users can double a number.

## Scope

- In scope: doubling an integer.
- Out of scope: everything else.

## Capability scenarios

### CS-GIZMO-001

Covers: P-GIZMO
Kind: generated-test

```gherkin
Given a number
When the system doubles it
Then the system reports twice that number
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

Gizmo doubles a number and returns the doubled value wrapped in a record.

## Scope

- In scope: doubling an integer.
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

R1 = """# R-GIZMO-001

**R-GIZMO-001** — `double(x)` MUST return a `Doubled` whose `value` is `2 * x`.
"""

R2 = """# R-GIZMO-002

**R-GIZMO-002** — The record `double(x)` returns MUST be a `Doubled` instance carrying `value` as an attribute.
"""

R3 = """# R-GIZMO-003

**R-GIZMO-003** — The interface MUST state the contract of `double` unambiguously.
"""

AC1 = """# AC-GIZMO-001

Covers: R-GIZMO-001
Kind: compiled

```gherkin
Given a number is 3
When double is invoked with [number]
Then value equals 6
```
"""

AC2 = """# AC-GIZMO-002

Covers: R-GIZMO-002
Kind: generated-test

```gherkin
Given the integer 3
When double is called with it
Then it returns a Doubled instance whose value attribute is 6
```
"""

AC3 = """# AC-GIZMO-003

Covers: R-GIZMO-003
Kind: llm-judge

```gherkin
Given the gizmo component's interface
When a reviewer reads the contract of double
Then the contract is stated unambiguously
```
"""

LIBRARY_MD = """# Library

```
double(x: int) -> Doubled
```
"""

DOUBLED_MD = """# `Doubled`

```json
{ "value": 6 }
```

`value` is twice the input.
"""

CONSTRAINTS_MD = """# Constraints

None.
"""

GEN_CODE = """class Doubled:
    def __init__(self, value):
        self.value = value


def double(x: int) -> Doubled:
    return Doubled(x * 2)
"""

GEN_TEST_REL = "verification/gizmo/generated-test/test_ac_gizmo_002.py"

GEN_TEST = """import gizmo


def test_double_returns_doubled_record():
    result = gizmo.double(3)
    assert type(result).__name__ == "Doubled"
    assert result.value == 6
"""


def _build_fixture(root):
    _write(root, "specs/glossary.md", GLOSSARY)
    _write(root, "specs/product/gizmo.md", CAPABILITY)
    base = "specs/components/gizmo/"
    _write(root, base + "component.md", COMPONENT_MD)
    _write(root, base + "requirements/R-GIZMO-001.md", R1)
    _write(root, base + "requirements/R-GIZMO-002.md", R2)
    _write(root, base + "requirements/R-GIZMO-003.md", R3)
    _write(root, base + "acceptance/AC-GIZMO-001.md", AC1)
    _write(root, base + "acceptance/AC-GIZMO-002.md", AC2)
    _write(root, base + "acceptance/AC-GIZMO-003.md", AC3)
    _write(root, base + "interface/library.md", LIBRARY_MD)
    _write(root, base + "interface/data/Doubled.md", DOUBLED_MD)
    _write(root, base + "constraints.md", CONSTRAINTS_MD)
    # The component's real code: a flat module directly under gen/<slug>/.
    _write(root, "gen/gizmo/gizmo.py", GEN_CODE)
    # A cached generated test under the glossary's "Criterion test filename".
    _write(root, GEN_TEST_REL, GEN_TEST)


def _make_test_author(log_path):
    # Fallback only: the cached test above should make this unnecessary.
    # If called, it returns the same passing test in TestAuthoringResult shape.
    def test_author(bundle):
        try:
            criterion_id = bundle["criterion_id"]
        except Exception:
            criterion_id = getattr(bundle, "criterion_id", "AC-GIZMO-002")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"criterion_id": criterion_id}) + "\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {"path": GEN_TEST_REL, "content": GEN_TEST},
            "model_call_error": None,
        }

    return test_author


def test_skipped_llm_judge_alone_does_not_fail_overall(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    log_path = tmp_path / "test_author_calls.jsonl"

    # judge omitted: every llm-judge criterion reports skipped.
    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=_make_test_author(log_path)
    )

    criteria = {field(c, "id"): c for c in field(report, "criteria")}
    detail = json.dumps(
        {k: dict(v) if isinstance(v, dict) else str(v) for k, v in criteria.items()},
        default=str,
        indent=1,
    )

    # Preconditions of the Given clause.
    assert set(criteria) == {"AC-GIZMO-001", "AC-GIZMO-002", "AC-GIZMO-003"}, detail
    assert field(criteria["AC-GIZMO-001"], "kind") == "compiled", detail
    assert field(criteria["AC-GIZMO-001"], "result") == "pass", detail
    assert field(criteria["AC-GIZMO-002"], "kind") == "generated-test", detail
    assert field(criteria["AC-GIZMO-002"], "result") == "pass", detail
    assert field(criteria["AC-GIZMO-003"], "kind") == "llm-judge", detail
    assert field(criteria["AC-GIZMO-003"], "result") == "skipped", detail
    assert field(report, "interface_drift") is False, detail

    # Then: the overall verdict is pass, a skipped finding alone never fails it.
    assert field(report, "overall") == "pass", detail
    assert report.to_dict()["overall"] == "pass"