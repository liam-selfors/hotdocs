"""AC-VERIFY-020: mutation_score is exactly 1/3 for three sites, one killed.

Covers R-VERIFY-006: a single component-wide mutation score, exactly four
operator families, one mutant per site. The fixture module has exactly
three mutation sites:

* ``a < b`` in ``g`` (comparison, swapped to ``>=``)
* ``a // b`` in ``h`` (binary op, swapped to ``%``)
* ``k in d`` in ``m`` (comparison, swapped to ``not in``)

``do_the_thing`` has no operators and no boolean constants. The one cached
generated-test test kills only the ``a < b`` mutant.
"""

from pathlib import Path

import pytest

import verifier_orchestrator


SLUG = "mutfix"
COMPONENT_ID = "comp-mutfix"
MODULE_NAME = "mutfix"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = """# Glossary

- **Mutfix** — a test term.
"""

PRODUCT = """---
id: P-MUTFIX
title: Mutfix capability
status: draft
owners: [team-a]
---

# Mutfix capability

## Purpose

Compare, divide and test membership of values.

## Scope

- In scope: comparing two numbers.
- Out of scope: everything else.

## Capability scenarios

### CS-MUTFIX-001

Covers: P-MUTFIX
Kind: compiled

```gherkin
Given a x is 1
When mutfix.g is invoked with [1, 2]
Then result equals true
```
"""

COMPONENT_MD = """---
id: comp-mutfix
title: Mutfix
status: draft
owners: [team-a]
realizes: [P-MUTFIX]
depends_on: []
---

# Mutfix

## Purpose

Mutfix compares two numbers, divides them, and tests membership.

## Scope

- In scope: g, h, m and do_the_thing.
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

REQUIREMENT = """# R-MUTFIX-001

**R-MUTFIX-001** — `g(a, b)` MUST return `a < b`.
"""

ACCEPTANCE = """# AC-MUTFIX-001

Covers: R-MUTFIX-001
Kind: generated-test

```gherkin
Given a is 1 and b is 2
When g(a, b) is called
Then it returns true
```
"""

LIBRARY_MD = """# Library

```
g(a, b) -> bool
h(a, b) -> int
m(k, d) -> bool
do_the_thing(x) -> object
```
"""

CONSTRAINTS = """# Constraints

None.
"""

MODULE_SOURCE = """def g(a, b):
    return a < b


def h(a, b):
    return a // b


def m(k, d):
    return k in d


def do_the_thing(x):
    return x
"""

# Passes against the original module; fails only against the `a < b` -> `a >= b`
# mutant. It never calls h or m, so their mutants survive.
CACHED_TEST = """import sys
from pathlib import Path

try:
    import mutfix
except ImportError:
    _root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(_root / "gen" / "mutfix"))
    import mutfix


def test_ac_mutfix_001():
    assert mutfix.g(1, 2) is True
"""


def _build_fixture(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "mutfix-cap.md", PRODUCT)
    comp = repo_root / "specs" / "components" / SLUG
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-MUTFIX-001.md", REQUIREMENT)
    _write(comp / "acceptance" / "AC-MUTFIX-001.md", ACCEPTANCE)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(repo_root / "gen" / SLUG / f"{MODULE_NAME}.py", MODULE_SOURCE)
    _write(
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_mutfix_001.py",
        CACHED_TEST,
    )


def test_ac_verify_020_mutation_score_is_one_third(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    score = field(report, "mutation_score")
    assert score is not None, "mutation_score must be reported for an unsealed component"
    # Three sites (a < b, a // b, k in d), exactly one killed (a < b).
    assert score == pytest.approx(1 / 3, abs=1e-9), (
        f"expected mutation_score exactly 1/3, got {score!r}"
    )