"""AC-VERIFY-015 (Covers: R-VERIFY-006).

Given a component with two generated-test-kind criteria, each testing a
different one of two functions in the same module, each test covering its
own function fully, when verify runs, then the reported mutation_score
reflects the union of both tests killing mutants (high), never either
test's own isolated score against the whole module (which would be far
lower).

Fixture design: the module `mathkit` has exactly six mutation sites under
the four permitted operators (no numeric constants are ever mutated, and the
module contains no boolean constants, `is`, or `in`):

    scale_sum: `a + b`, `(...) * c`, `(...) - a`        -> 3 mutants
    in_range:  `n >= lo`, `n < hi`, `... and ...`       -> 3 mutants

AC-MATHKIT-001's test kills exactly the three scale_sum mutants, and
AC-MATHKIT-002's test kills exactly the three in_range mutants. Either
test's isolated score against the whole module is therefore 3/6 = 0.5,
while the union score is 6/6 = 1.0.
"""

import verifier_orchestrator

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY = """# Glossary

- **Foo** — a test term.
"""

CAPABILITY = """---
id: P-MATHKIT
title: Math kit
status: draft
owners: [team-a]
---

# Math kit

## Purpose

Provides small arithmetic helpers.

## Scope

- In scope: arithmetic helpers.
- Out of scope: everything else.

## Capability scenarios

### CS-MATHKIT-001

Covers: P-MATHKIT
Kind: compiled

```gherkin
Given a n is 5
When mathkit.in_range is invoked with [5, 0, 10]
Then result equals true
```
"""

COMPONENT = """---
id: comp-mathkit
title: Math kit
status: draft
owners: [team-a]
realizes: [P-MATHKIT]
depends_on: []
---

# Math kit

## Purpose

Math kit provides two small arithmetic helpers.

## Scope

- In scope: the two helpers.
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

R1 = """# R-MATHKIT-001

**R-MATHKIT-001** — `scale_sum(a, b, c)` MUST return `(a + b) * c - a`.
"""

R2 = """# R-MATHKIT-002

**R-MATHKIT-002** — `in_range(n, lo, hi)` MUST return whether `lo <= n < hi`.
"""

AC1 = """# AC-MATHKIT-001

Covers: R-MATHKIT-001
Kind: generated-test

```gherkin
Given numbers a = 2, b = 5 and c = 3
When scale_sum(a, b, c) is called
Then it returns 19
```
"""

AC2 = """# AC-MATHKIT-002

Covers: R-MATHKIT-002
Kind: generated-test

```gherkin
Given a bound lo = 0 and hi = 10
When in_range(n, lo, hi) is called for several n
Then it is true exactly for lo <= n < hi
```
"""

LIBRARY = """# Library

```
scale_sum(a: int, b: int, c: int) -> int
in_range(n: int, lo: int, hi: int) -> bool
```
"""

CONSTRAINTS = """# Constraints

None.
"""

MODULE = """def scale_sum(a, b, c):
    return (a + b) * c - a


def in_range(n, lo, hi):
    return n >= lo and n < hi
"""

IMPORT_PRELUDE = """import sys
from pathlib import Path

try:
    import mathkit
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parents[3] / "gen" / "mathkit"))
    import mathkit
"""

TEST1 = IMPORT_PRELUDE + """

def test_scale_sum():
    assert mathkit.scale_sum(2, 5, 3) == 19
    assert mathkit.scale_sum(1, 1, 1) == 1
    assert mathkit.scale_sum(4, 2, 2) == 8
"""

TEST2 = IMPORT_PRELUDE + """

def test_in_range():
    assert mathkit.in_range(5, 0, 10)
    assert mathkit.in_range(0, 0, 10)
    assert not mathkit.in_range(-1, 0, 10)
    assert not mathkit.in_range(10, 0, 10)
    assert not mathkit.in_range(11, 0, 10)
"""

CACHED_TESTS = {
    "AC-MATHKIT-001": TEST1,
    "AC-MATHKIT-002": TEST2,
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _test_filename(criterion_id: str) -> str:
    return "test_" + criterion_id.lower().replace("-", "_") + ".py"


def _build_fixture(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "P-MATHKIT.md", CAPABILITY)
    comp = repo_root / "specs" / "components" / "mathkit"
    _write(comp / "component.md", COMPONENT)
    _write(comp / "requirements" / "R-MATHKIT-001.md", R1)
    _write(comp / "requirements" / "R-MATHKIT-002.md", R2)
    _write(comp / "acceptance" / "AC-MATHKIT-001.md", AC1)
    _write(comp / "acceptance" / "AC-MATHKIT-002.md", AC2)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(repo_root / "gen" / "mathkit" / "mathkit.py", MODULE)
    gt_dir = repo_root / "verification" / "mathkit" / "generated-test"
    for cid, content in CACHED_TESTS.items():
        _write(gt_dir / _test_filename(cid), content)


def _fake_test_author(bundle):
    # Fallback only: each criterion already has a cached test, so this should
    # not normally be called. If it is, it returns the same tests, in
    # test-author's documented TestAuthoringResult shape.
    cid = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id")
    return {
        "component_id": "comp-mathkit",
        "criterion_id": cid,
        "model": "fake-model",
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/mathkit/generated-test/" + _test_filename(cid),
            "content": CACHED_TESTS[cid],
        },
        "model_call_error": None,
    }


def test_mutation_score_is_union_across_generated_test_criteria(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = verifier_orchestrator.verify(
        "comp-mathkit", repo_root, test_author=_fake_test_author
    )

    # Both generated-test criteria are reported, and each test passes
    # against the unmutated module.
    criteria = field(report, "criteria")
    by_id = {c["id"]: c for c in criteria}
    assert "AC-MATHKIT-001" in by_id
    assert "AC-MATHKIT-002" in by_id
    assert by_id["AC-MATHKIT-001"]["kind"] == "generated-test"
    assert by_id["AC-MATHKIT-002"]["kind"] == "generated-test"
    assert by_id["AC-MATHKIT-001"]["result"] == "pass"
    assert by_id["AC-MATHKIT-002"]["result"] == "pass"

    score = field(report, "mutation_score")

    # Exactly one number for the whole component.
    assert score is not None
    assert isinstance(score, (int, float)) and not isinstance(score, bool)

    # Either test alone, against the whole module, kills 3 of 6 mutants.
    isolated_score = 3 / 6
    # Their union kills all 6.
    assert score > isolated_score
    assert score >= 0.8
    assert abs(score - 1.0) < 1e-9