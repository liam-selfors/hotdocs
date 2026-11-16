import verifier_orchestrator

import threading
import time
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY = """# Glossary

- **Foo** — a test term.
"""

PRODUCT = """---
id: P-COUNTING
title: Counting
status: draft
owners: [team-a]
---

# Counting

## Purpose

Count up from zero to a number.

## Scope

- In scope: counting up to a number.
- Out of scope: everything else.

## Capability scenarios

### CS-COUNTING-001

Covers: P-COUNTING
Kind: generated-test

```gherkin
Given a number 3
When counting runs
Then it reaches 3
```
"""

COMPONENT = """---
id: comp-counter
title: Counter
status: draft
owners: [team-a]
depends_on: []
realizes: [P-COUNTING]
---

# Counter

## Purpose

Counter counts up from zero to a number.

## Scope

- In scope: counting up to a number.
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

REQUIREMENT = """# R-COUNTER-001

**R-COUNTER-001** — `count_to(x)` MUST count up from 0 in steps of 1 while below `x` and return the final count (0 when `x` is at most 0).
"""

ACCEPTANCE = """# AC-COUNTER-001

Covers: R-COUNTER-001
Kind: generated-test

```gherkin
Given x is 3
When count_to(x) is called
Then it returns 3
```
"""

LIBRARY = """# Library

```
count_to(x: int) -> int
```
"""

CONSTRAINTS = """# Constraints

None.
"""

CANDIDATE = """def count_to(x):
    i = 0
    while i < x:
        i = i + 1
    return i
"""

# The one generated test covering the loop. Imports the module by name so
# that the PYTHONPATH the runner sets (the mutated copy for a mutant run)
# wins; the appended relative entry is only a fallback for the unmutated run.
GENERATED_TEST = """import sys

sys.path.append("gen/counter")

import counter


def test_count_to_three():
    assert counter.count_to(3) == 3


def test_count_to_one():
    assert counter.count_to(1) == 1


def test_count_to_zero():
    assert counter.count_to(0) == 0
"""


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path):
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "counting.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "counter"
    _write(comp / "component.md", COMPONENT)
    _write(comp / "requirements" / "R-COUNTER-001.md", REQUIREMENT)
    _write(comp / "acceptance" / "AC-COUNTER-001.md", ACCEPTANCE)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(repo_root / "gen" / "counter" / "counter.py", CANDIDATE)
    _write(
        repo_root / "verification" / "counter" / "generated-test" / "test_ac_counter_001.py",
        GENERATED_TEST,
    )


def _fallback_test_author(bundle):
    # Only used if the cached generated test were somehow not picked up;
    # returns the same test, in TestAuthoringResult's documented shape.
    return {
        "component_id": "comp-counter",
        "criterion_id": "AC-COUNTER-001",
        "model": "fake-model",
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/counter/generated-test/test_ac_counter_001.py",
            "content": GENERATED_TEST,
        },
        "model_call_error": None,
    }


def test_non_terminating_mutant_times_out_and_counts_as_killed(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    outcome = {}

    def run():
        try:
            outcome["report"] = verifier_orchestrator.verify(
                "comp-counter", repo_root, test_author=_fallback_test_author
            )
        except BaseException as exc:  # surfaced to the main thread below
            outcome["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    start = time.monotonic()
    worker.start()
    worker.join(timeout=10.0)
    elapsed = time.monotonic() - start

    # Then: verify returns within ten seconds, despite a mutant
    # (e.g. `i = i - 1`) that makes the loop never terminate.
    assert not worker.is_alive(), "verify did not return within ten seconds"
    assert elapsed < 10.0, f"verify took {elapsed:.2f}s"
    if "error" in outcome:
        raise outcome["error"]

    report = outcome["report"]

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-COUNTER-001"]
    assert len(matching) == 1
    # The unmutated run terminates normally and passes.
    assert field(matching[0], "result") == "pass"

    # Every terminating mutant of this function is killed by the test's exact
    # return-value assertions, so any mutant left unkilled would be the
    # non-terminating one: a timed-out mutant must count as killed.
    score = field(report, "mutation_score")
    assert score is not None
    assert abs(float(score) - 1.0) < 1e-9, f"mutation_score was {score}"