import os
import signal
import sys
import time
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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

Count up to a number.

## Scope

- In scope: counting up to a number.
- Out of scope: everything else.

## Capability scenarios

### CS-COUNTING-001

Covers: P-COUNTING
Kind: llm-judge

```gherkin
Given a number
When it is counted up to
Then the count equals the number
```
"""

COMPONENT = """---
id: comp-tally
title: Tally
status: draft
owners: [team-a]
realizes: [P-COUNTING]
depends_on: []
---

# Tally

## Purpose

Tally counts up from zero to a number.

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

REQUIREMENT = """# R-TALLY-001

**R-TALLY-001** — `count_up(x)` MUST count up from zero by one while the
count is less than `x`, and return the final count.
"""

ACCEPTANCE = """# AC-TALLY-001

Covers: R-TALLY-001
Kind: generated-test

```gherkin
Given x = 3
When count_up(x) is called
Then it returns 3
```
"""

LIBRARY = """# Library

```
count_up(x: int) -> int
```
"""

CONSTRAINTS = """# Constraints

None.
"""

CANDIDATE = """def count_up(x):
    i = 0
    while i < x:
        i = i + 1
    return i
"""

GENERATED_TEST = """import os
import sys
from pathlib import Path

sys.path.append(os.path.join("gen", "tally"))
try:
    sys.path.append(str(Path(__file__).resolve().parents[3] / "gen" / "tally"))
except IndexError:
    pass

import tally


def test_count_up_counts_to_x():
    assert tally.count_up(3) == 3
    assert tally.count_up(1) == 1
    assert tally.count_up(0) == 0
    assert tally.count_up(-2) == 0
"""


def _build_fixture(repo_root):
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "counting.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "tally"
    _write(comp / "component.md", COMPONENT)
    _write(comp / "requirements" / "R-TALLY-001.md", REQUIREMENT)
    _write(comp / "acceptance" / "AC-TALLY-001.md", ACCEPTANCE)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(repo_root / "gen" / "tally" / "tally.py", CANDIDATE)
    _write(
        repo_root / "verification" / "tally" / "generated-test" / "test_ac_tally_001.py",
        GENERATED_TEST,
    )


class _HangGuard(BaseException):
    pass


def test_nonterminating_mutant_times_out_and_counts_as_killed(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    use_alarm = hasattr(signal, "SIGALRM")
    old_handler = None
    if use_alarm:
        def _on_alarm(signum, frame):
            raise _HangGuard("verify did not return (hang guard fired)")

        old_handler = signal.signal(signal.SIGALRM, _on_alarm)
        signal.alarm(12)

    start = time.monotonic()
    try:
        report = verifier_orchestrator.verify("comp-tally", repo_root)
    except _HangGuard as exc:
        raise AssertionError(
            "verify did not return within ten seconds: %s" % exc
        ) from None
    finally:
        if use_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    elapsed = time.monotonic() - start

    assert elapsed < 10, "verify took %.2f seconds, expected under 10" % elapsed

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-TALLY-001"]
    assert len(matching) == 1, "expected exactly one AC-TALLY-001 entry, got %r" % (criteria,)
    criterion = matching[0]
    assert field(criterion, "kind") == "generated-test"
    assert field(criterion, "result") == "pass", (
        "the generated test passes on unmutated code, so the criterion must pass; got %r"
        % (criterion,)
    )

    score = field(report, "mutation_score")
    assert score is not None, "an unsealed component must report a mutation_score"
    # Every mutant of count_up is killed by the generated test either by an
    # assertion failure/error or, for the non-terminating loop mutant(s), by
    # the wall-clock timeout. A timed-out mutant counts as killed, so the
    # score must be perfect.
    assert abs(float(score) - 1.0) < 1e-9, (
        "expected every mutant (including the non-terminating one) to count as "
        "killed, got mutation_score=%r" % (score,)
    )