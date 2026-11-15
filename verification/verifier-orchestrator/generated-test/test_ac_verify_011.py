"""AC-VERIFY-011: requirement_results projects criterion results onto R-ids.

Given a component with two criteria covering R-FOO-001 (both pass), one
criterion covering R-FOO-002 (fails), and an llm-judge criterion covering
R-FOO-003 that is skipped (no judge configured), verify's
requirement_results is exactly
{"R-FOO-001": "pass", "R-FOO-002": "fail", "R-FOO-003": "fail"} and carries
nothing but R-id keys and pass/fail values.
"""

import json
import re
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = """# Glossary

- **Foo** — a test term.
"""

PRODUCT = """---
id: P-DOUBLING
title: Doubling
status: draft
owners: [team-a]
---

# Doubling

## Purpose

Doubling numbers on request.

## Scope

- In scope: doubling an integer.
- Out of scope: everything else.

## Capability scenarios

### CS-DOUBLING-001

Covers: P-DOUBLING
Kind: generated-test

```gherkin
Given the assembled system
When a caller asks it to double 2
Then it answers 4
```
"""

COMPONENT = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
depends_on: []
realizes: [P-DOUBLING]
---

# Foo

## Purpose

Foo doubles a number.

## Scope

- In scope: doubling integers.
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

REQ_001 = """# R-FOO-001

**R-FOO-001** — `double_it(x)` MUST return `2 * x`.
"""

REQ_002 = """# R-FOO-002

**R-FOO-002** — `double_it(3)` MUST return `6`.
"""

REQ_003 = """# R-FOO-003

**R-FOO-003** — The foo spec MUST be clear and free of contradiction.
"""

LIBRARY = """# Library

```
double_it(x: int) -> int
```
"""

CONSTRAINTS = """# Constraints

None.
"""

AC_001 = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x is the number 2
When double_it is called with x
Then it returns 4
```
"""

AC_002 = """# AC-FOO-002

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x is the number 5
When double_it is called with x
Then it returns 10
```
"""

AC_003 = """# AC-FOO-003

Covers: R-FOO-002
Kind: generated-test

```gherkin
Given x is the number 3
When double_it is called with x
Then it returns 6
```
"""

AC_004 = """# AC-FOO-004

Covers: R-FOO-003
Kind: llm-judge

```gherkin
Given the foo component's spec
When a reviewer reads it
Then it is clear and free of contradiction
```
"""

GEN_MODULE = '''def double_it(x):
    """Return twice x, except deliberately wrong for 3."""
    if x == 3:
        return 7
    return 2 * x
'''

TEST_CONTENT = {
    "AC-FOO-001": (
        "import foo\n"
        "\n"
        "\n"
        "def test_ac_foo_001():\n"
        "    assert foo.double_it(2) == 4\n"
    ),
    "AC-FOO-002": (
        "import foo\n"
        "\n"
        "\n"
        "def test_ac_foo_002():\n"
        "    assert foo.double_it(5) == 10\n"
    ),
    "AC-FOO-003": (
        "import foo\n"
        "\n"
        "\n"
        "def test_ac_foo_003():\n"
        "    assert foo.double_it(3) == 6\n"
    ),
}


def _test_filename(criterion_id: str) -> str:
    return "test_" + criterion_id.lower().replace("-", "_") + ".py"


def _build_fixture(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "doubling.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT)
    _write(comp / "requirements" / "R-FOO-001.md", REQ_001)
    _write(comp / "requirements" / "R-FOO-002.md", REQ_002)
    _write(comp / "requirements" / "R-FOO-003.md", REQ_003)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_001)
    _write(comp / "acceptance" / "AC-FOO-002.md", AC_002)
    _write(comp / "acceptance" / "AC-FOO-003.md", AC_003)
    _write(comp / "acceptance" / "AC-FOO-004.md", AC_004)

    # The component's real code.
    _write(repo_root / "gen" / "foo" / "foo.py", GEN_MODULE)

    # Cached generated tests, at the glossary's "Criterion test filename".
    gt_dir = repo_root / "verification" / "foo" / "generated-test"
    for cid, content in TEST_CONTENT.items():
        _write(gt_dir / _test_filename(cid), content)


def _make_test_author():
    """A test_author in the injected single-bundle-arg shape (D65).

    Only a safety net in case verify decides to re-author instead of using
    the cached tests: it returns the very same test content, so each
    generated-test criterion's outcome is the same either way.
    """

    def test_author(bundle):
        cid = field(bundle, "criterion_id")
        return {
            "component_id": "comp-foo",
            "criterion_id": cid,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/foo/generated-test/" + _test_filename(cid),
                "content": TEST_CONTENT[cid],
            },
            "model_call_error": None,
        }

    return test_author


EXPECTED = {"R-FOO-001": "pass", "R-FOO-002": "fail", "R-FOO-003": "fail"}

FORBIDDEN_SUBSTRINGS = [
    "Given",
    "When",
    "Then",
    "gherkin",
    "double_it",
    "rationale",
    "expected",
    "actual",
    "failure_detail",
    "message",
    "AC-FOO",
    "returns",
]


def _assert_boolean_only(req_results):
    assert isinstance(req_results, dict)
    for key, value in req_results.items():
        assert isinstance(key, str)
        assert re.fullmatch(r"R-[A-Z0-9]+-\d{3}", key), key
        assert value in ("pass", "fail"), (key, value)
    dumped = json.dumps(req_results, sort_keys=True)
    for needle in FORBIDDEN_SUBSTRINGS:
        assert needle not in dumped, (needle, dumped)
    # Values are bare strings only, never nested structures.
    for value in req_results.values():
        assert not isinstance(value, (dict, list, tuple))


def test_requirement_results_projects_and_is_boolean_only(tmp_path):
    repo_root = tmp_path
    _build_fixture(repo_root)

    report = verifier_orchestrator.verify(
        "comp-foo", repo_root, test_author=_make_test_author()
    )

    # Sanity: the per-criterion outcomes are the ones the Given describes.
    criteria = field(report, "criteria")
    results = {field(c, "id"): field(c, "result") for c in criteria}
    assert results.get("AC-FOO-001") == "pass", results
    assert results.get("AC-FOO-002") == "pass", results
    assert results.get("AC-FOO-003") == "fail", results
    assert results.get("AC-FOO-004") == "skipped", results

    req_results = field(report, "requirement_results")
    assert dict(req_results) == EXPECTED
    _assert_boolean_only(dict(req_results))

    # The JSON form carries the same, equally boolean-only field.
    if hasattr(report, "to_dict"):
        as_dict = report.to_dict()
        rr = field(as_dict, "requirement_results")
        assert dict(rr) == EXPECTED
        _assert_boolean_only(dict(rr))