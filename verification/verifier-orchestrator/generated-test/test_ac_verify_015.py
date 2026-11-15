import verifier_orchestrator

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = """# Glossary

- **Foo** — a test term.
"""

PRODUCT = """---
id: P-CALC
title: Calc capability
status: draft
owners: [team-a]
---

# Calc capability

## Purpose

Calc computes small arithmetic and classification results.

## Scope

- In scope: arithmetic helpers.
- Out of scope: everything else.

## Capability scenarios

### CS-CALC-001

Covers: P-CALC
Kind: llm-judge

```gherkin
Given a pair of numbers
When the calc capability is used
Then a result is returned
```
"""

COMPONENT = """---
id: comp-calc
title: Calc
status: draft
owners: [team-a]
depends_on: []
realizes: [P-CALC]
---

# Calc

## Purpose

Calc combines two numbers and checks a number against a flag.

## Scope

- In scope: the `combine` and `check` functions.
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

REQ_1 = """# R-CALC-001

**R-CALC-001** — `combine(a, b)` MUST compute `total = a + b` and return
`total * b` when `total > a`, otherwise `total // b`.
"""

REQ_2 = """# R-CALC-002

**R-CALC-002** — `check(x, flag)` MUST return `True` when `x == 0` or
`flag` is true, otherwise whether `x < 5`.
"""

AC_1 = """# AC-CALC-001

Covers: R-CALC-001
Kind: generated-test

```gherkin
Given two numbers a and b
When combine is called with them
Then it returns the combined value described by R-CALC-001
```
"""

AC_2 = """# AC-CALC-002

Covers: R-CALC-002
Kind: generated-test

```gherkin
Given a number x and a flag
When check is called with them
Then it returns the classification described by R-CALC-002
```
"""

LIBRARY = """# Library

```
combine(a: int, b: int) -> int
check(x: int, flag: bool) -> bool
```
"""

CONSTRAINTS = """# Constraints

None.
"""

# Exactly eight mutation sites: four in combine, four in check.
MODULE = """def combine(a, b):
    total = a + b
    if total > a:
        return total * b
    return total // b


def check(x, flag):
    if x == 0 or flag:
        return True
    return x < 5
"""

# Kills all four combine mutants; never calls check.
TEST_1 = """import calc


def test_combine_fully():
    assert calc.combine(2, 3) == 15
    assert calc.combine(4, -2) == -1
"""

# Kills all four check mutants; never calls combine.
TEST_2 = """import calc


def test_check_fully():
    assert calc.check(7, False) == False
    assert calc.check(7, True) == True
    assert calc.check(0, False) == True
"""

TESTS = {
    "AC-CALC-001": ("verification/calc/generated-test/test_ac_calc_001.py", TEST_1),
    "AC-CALC-002": ("verification/calc/generated-test/test_ac_calc_002.py", TEST_2),
}


def _build_fixture(repo_root: Path):
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "calc.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "calc"
    _write(comp / "component.md", COMPONENT)
    _write(comp / "requirements" / "R-CALC-001.md", REQ_1)
    _write(comp / "requirements" / "R-CALC-002.md", REQ_2)
    _write(comp / "acceptance" / "AC-CALC-001.md", AC_1)
    _write(comp / "acceptance" / "AC-CALC-002.md", AC_2)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(repo_root / "gen" / "calc" / "calc.py", MODULE)
    for rel, content in TESTS.values():
        _write(repo_root / rel, content)


def _fake_test_author(bundle):
    # Fallback only: the tests are already cached, but if the orchestrator
    # dispatches anyway it receives the very same test content.
    cid = field(bundle, "criterion_id")
    rel, content = TESTS[cid]
    return {
        "component_id": "comp-calc",
        "criterion_id": cid,
        "model": "fake-model",
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": rel, "content": content},
        "model_call_error": None,
    }


def test_mutation_score_is_union_across_generated_test_criteria(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = verifier_orchestrator.verify(
        "comp-calc", repo_root, test_author=_fake_test_author
    )

    criteria = field(report, "criteria")
    by_id = {c["id"]: c for c in criteria}
    assert "AC-CALC-001" in by_id and "AC-CALC-002" in by_id
    # Both tests pass against the unmutated module (sanity: they really ran).
    assert by_id["AC-CALC-001"]["result"] == "pass", by_id["AC-CALC-001"]
    assert by_id["AC-CALC-002"]["result"] == "pass", by_id["AC-CALC-002"]

    score = field(report, "mutation_score")
    assert score is not None
    assert isinstance(score, (int, float)) and not isinstance(score, bool)

    # Each test alone kills only its own function's 4 of the 8 mutants,
    # i.e. an isolated (or averaged) score against the whole module is 0.5.
    # The union of both tests kills all 8.
    assert score > 0.5, (
        "mutation_score %r looks like an isolated/averaged per-test score, "
        "not the union across both generated-test files" % (score,)
    )
    assert 0.9 <= score <= 1.0, (
        "expected the union mutation score to be high (all mutants killed by "
        "some test), got %r" % (score,)
    )