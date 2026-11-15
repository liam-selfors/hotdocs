"""AC-VERIFY-006: a generated-test criterion whose mutation score is below the
published bar makes the overall verdict ``fail``, and the report cites the
mutation-score shortfall (R-VERIFY-006)."""

import sys
from pathlib import Path

import pytest

import verifier_orchestrator


SLUG = "mutscore"
COMPONENT_ID = "comp-mutscore"
MODULE_NAME = "mutscore"
CRITERION_ID = "AC-MUTSCORE-001"
REQUIREMENT_ID = "R-MUTSCORE-001"
CAPABILITY_ID = "P-MUTSCORE"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY = """# Glossary

- **Helper** — a small pure function.
"""

CAPABILITY = """---
id: P-MUTSCORE
title: Mutscore helpers
status: draft
owners: [team-a]
---

# Mutscore helpers

## Purpose

Offers small arithmetic and boolean helpers.

## Scope

- In scope: the helpers.
- Out of scope: everything else.

## Capability scenarios

### CS-MUTSCORE-001

Covers: P-MUTSCORE
Kind: generated-test

```gherkin
Given the mutscore helpers
When add is called with 2 and 3
Then it returns 5
```
"""

COMPONENT_MD = """---
id: comp-mutscore
title: Mutscore
status: draft
owners: [team-a]
depends_on: []
realizes: [P-MUTSCORE]
---

# Mutscore

## Purpose

Mutscore offers small arithmetic and boolean helpers.

## Scope

- In scope: the helper functions declared in the interface.
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

REQUIREMENT_MD = """# R-MUTSCORE-001

**R-MUTSCORE-001** — `add(a, b)` MUST return `a + b`; `is_large(x)` MUST
return whether `x > 10`; `both(a, b)` MUST return `a and b`; `same(a, b)`
MUST return whether `a == b`.
"""

ACCEPTANCE_MD = """# AC-MUTSCORE-001

Covers: R-MUTSCORE-001
Kind: generated-test

```gherkin
Given the mutscore helper functions
When add is called with 2 and 3
Then it returns 5
```
"""

LIBRARY_MD = """# Library

```
add(a: int, b: int) -> int
is_large(x: int) -> bool
both(a: bool, b: bool) -> bool
same(a: int, b: int) -> bool
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""

# Six mutation sites under the four operators: `+`, `>`, `True`, `False`,
# `and`, `==`.  The cached test below kills only the `+` mutant.
CANDIDATE_PY = """def add(a: int, b: int) -> int:
    return a + b


def is_large(x: int) -> bool:
    if x > 10:
        return True
    return False


def both(a: bool, b: bool) -> bool:
    return a and b


def same(a: int, b: int) -> bool:
    return a == b
"""

# A weak but passing cached generated test: passes against the real candidate,
# survives every mutant except the `+` -> `-` one.
CACHED_TEST_PY = """import mutscore


def test_add_two_and_three():
    assert mutscore.add(2, 3) == 5
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    _write(root / "specs" / "glossary.md", GLOSSARY)
    _write(root / "specs" / "product" / "mutscore.md", CAPABILITY)
    comp = root / "specs" / "components" / SLUG
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / f"{REQUIREMENT_ID}.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / f"{CRITERION_ID}.md", ACCEPTANCE_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(root / "gen" / SLUG / f"{MODULE_NAME}.py", CANDIDATE_PY)
    _write(
        root / "verification" / SLUG / "generated-test" / "test_ac_mutscore_001.py",
        CACHED_TEST_PY,
    )
    saved = sys.modules.pop(MODULE_NAME, None)
    yield root
    sys.modules.pop(MODULE_NAME, None)
    if saved is not None:
        sys.modules[MODULE_NAME] = saved


def test_mutation_score_below_bar_fails_overall_verdict(repo_root):
    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    # The criterion's own test passes against the unmutated candidate, so any
    # overall failure must come from the mutation-score shortfall.
    criteria = field(report, "criteria")
    by_id = {field(c, "id"): c for c in criteria}
    assert CRITERION_ID in by_id, f"criterion missing from report: {criteria!r}"
    entry = by_id[CRITERION_ID]
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == "pass", entry
    assert all(field(c, "result") != "fail" for c in criteria), criteria
    assert not field(report, "interface_drift")

    # The report cites the shortfall: one component-wide score, below 80%.
    score = field(report, "mutation_score")
    assert score is not None
    assert isinstance(score, (int, float)) and not isinstance(score, bool)
    assert 0.0 <= score < 0.80, score

    # And the overall verdict is fail.
    assert field(report, "overall") == "fail"

    # The JSON form carries the same cited score and verdict.
    if hasattr(report, "to_dict"):
        as_dict = report.to_dict()
        assert as_dict["overall"] == "fail"
        assert as_dict["mutation_score"] == pytest.approx(score)
        assert as_dict["mutation_score"] < 0.80