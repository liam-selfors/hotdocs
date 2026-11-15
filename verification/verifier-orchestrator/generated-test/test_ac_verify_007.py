import dataclasses
import json
from pathlib import Path

import pytest

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


COMPONENT_MD = """---
id: comp-widget
title: Widget
status: draft
owners: [team-a]
realizes: [P-WIDGET]
depends_on: []
---

# Widget

## Purpose

Widget doubles a number.

## Scope

- In scope: doubling integers.
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

PRODUCT_MD = """---
id: P-WIDGET
title: Widget capability
status: draft
owners: [team-a]
---

# Widget capability

## Purpose

The system can double a number.

## Scope

- In scope: doubling.

## Capability scenarios

### CS-WIDGET-001

Covers: P-WIDGET

```gherkin
Given a number 2
When the system doubles it
Then the answer is 4
```
"""

GLOSSARY_MD = """# Glossary

- **Foo** — a test term.
"""

R1 = """# R-WIDGET-001

**R-WIDGET-001** — `double_it(x)` MUST return `2 * x`.
"""

R2 = """# R-WIDGET-002

**R-WIDGET-002** — The Purpose section MUST be clear and unambiguous.
"""

AC1 = """# AC-WIDGET-001

Covers: R-WIDGET-001
Kind: generated-test

```gherkin
Given x = 2
When double_it(x) is called
Then it returns 4
```
"""

AC2 = """# AC-WIDGET-002

Covers: R-WIDGET-002
Kind: llm-judge

```gherkin
Given the widget component spec
When a reviewer reads its Purpose section
Then the Purpose is clear and unambiguous
```
"""

LIBRARY_MD = """# Library

```
double_it(x: int) -> int
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""

GEN_CODE = '''def double_it(x):
    return 2 * x
'''

CACHED_TEST = '''import sys
from pathlib import Path

_gen = Path(__file__).resolve().parents[3] / "gen" / "widget"
if str(_gen) not in sys.path:
    sys.path.append(str(_gen))

import widget


def test_double_it_two():
    assert widget.double_it(2) == 4


def test_double_it_negative():
    assert widget.double_it(-3) == -6
'''


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path):
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    _write(repo_root / "specs" / "product" / "widget.md", PRODUCT_MD)
    comp = repo_root / "specs" / "components" / "widget"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-WIDGET-001.md", R1)
    _write(comp / "requirements" / "R-WIDGET-002.md", R2)
    _write(comp / "acceptance" / "AC-WIDGET-001.md", AC1)
    _write(comp / "acceptance" / "AC-WIDGET-002.md", AC2)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(repo_root / "gen" / "widget" / "widget.py", GEN_CODE)
    _write(
        repo_root / "verification" / "widget" / "generated-test" / "test_ac_widget_001.py",
        CACHED_TEST,
    )


EXPECTED_IDS = ["AC-WIDGET-001", "AC-WIDGET-002"]
VALID_RESULTS = {"pass", "fail", "skipped"}


def _check_report_dict(d):
    assert isinstance(d, dict)
    for key in ("component_id", "criteria", "mutation_score", "interface_drift", "overall"):
        assert key in d, f"report missing {key!r}"
    assert d["component_id"] == "comp-widget"
    criteria = d["criteria"]
    assert isinstance(criteria, list)
    ids = sorted(c["id"] for c in criteria)
    assert ids == EXPECTED_IDS
    for c in criteria:
        assert c["result"] in VALID_RESULTS
    ms = d["mutation_score"]
    assert ms is None or (isinstance(ms, (int, float)) and not isinstance(ms, bool) and 0 <= ms <= 1)
    assert isinstance(d["interface_drift"], bool)
    assert d["overall"] in {"pass", "fail"}


def test_verify_returns_exactly_one_verification_report(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = verifier_orchestrator.verify("comp-widget", repo_root)

    # Exactly one report: a single dataclass instance, not a collection or bare dict.
    assert not isinstance(report, (list, tuple, set, dict))
    assert dataclasses.is_dataclass(report) and not isinstance(report, type)

    for name in ("criteria", "mutation_score", "interface_drift", "overall"):
        assert has_field(report, name), f"report missing {name!r}"

    criteria = field(report, "criteria")
    assert isinstance(criteria, list)
    ids = sorted(c["id"] for c in criteria)
    assert ids == EXPECTED_IDS
    by_id = {c["id"]: c for c in criteria}
    for c in criteria:
        assert isinstance(c, dict)
        assert c["result"] in VALID_RESULTS
    # llm-judge with no judge configured reports skipped.
    assert by_id["AC-WIDGET-002"]["result"] == "skipped"

    ms = field(report, "mutation_score")
    assert ms is None or (isinstance(ms, (int, float)) and not isinstance(ms, bool) and 0 <= ms <= 1)
    assert isinstance(field(report, "interface_drift"), bool)
    assert field(report, "overall") in {"pass", "fail"}

    d = report.to_dict()
    _check_report_dict(d)
    assert d["overall"] == field(report, "overall")
    # JSON-serializable as one object.
    _check_report_dict(json.loads(json.dumps(d)))


def test_cli_json_prints_exactly_one_report(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    try:
        code = verifier_orchestrator.main(
            ["comp-widget", "--repo-root", str(repo_root), "--format=json"]
        )
    except SystemExit as exc:
        code = exc.code

    out = capsys.readouterr().out
    # json.loads rejects concatenated documents, so this proves exactly one report.
    d = json.loads(out)
    _check_report_dict(d)
    assert code == (0 if d["overall"] == "pass" else 1)