"""AC-VERIFY-010 (Covers: R-VERIFY-010).

Given a component with one generated-test-kind criterion, no cached test,
  and no test_author configured
When verify runs
Then that criterion's result is fail, not skipped, and the overall verdict
  is fail
"""

import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY = """# Glossary

- **Widget** — a test term.
"""

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

- In scope: doubling an integer.
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

REQUIREMENT_MD = """# R-WIDGET-001

**R-WIDGET-001** — `double(x)` MUST return `2 * x`.
"""

ACCEPTANCE_MD = """# AC-WIDGET-001

Covers: R-WIDGET-001
Kind: generated-test

```gherkin
Given x = 2
When double(x) is called
Then it returns 4
```
"""

LIBRARY_MD = """# Library

```
double(x: int) -> int
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""

PRODUCT_MD = """---
id: P-WIDGET
title: Widget Doubling
status: draft
owners: [team-a]
---

# Widget Doubling

## Purpose

Numbers can be doubled.

## Scope

- In scope: doubling an integer.

## Capability scenarios

### CS-WIDGET-001

Covers: P-WIDGET
Kind: llm-judge

```gherkin
Given a number
When it is doubled
Then the result is twice the number
```
"""

GEN_WIDGET = '''def double(x):
    return 2 * x
'''

FAKE_ASSEMBLER = '''import json
from pathlib import Path

_LOG = {log_path!r}


def _log(record):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


class _Bundle(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _read(path):
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def assemble(component_id, repo_root, mode="cold"):
    _log({{"fn": "assemble", "component_id": component_id, "mode": mode}})
    root = Path(repo_root)
    base = root / "specs" / "components" / "widget"
    return _Bundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec=_read(base / "component.md") + "\\n\\n" + _read(base / "requirements" / "R-WIDGET-001.md"),
        interface=_read(base / "interface" / "library.md"),
        constraints=_read(base / "constraints.md"),
        dependency_interfaces={{}},
        dependency_context={{}},
        dependency_usage={{}},
        vars={{}},
        glossary=_read(root / "specs" / "glossary.md"),
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log({{"fn": "assemble_criterion", "component_id": component_id, "criterion_id": criterion_id}})
    root = Path(repo_root)
    base = root / "specs" / "components" / "widget"
    return _Bundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-WIDGET-001",
        criterion_text=_read(base / "acceptance" / "AC-WIDGET-001.md"),
        requirement_text=_read(base / "requirements" / "R-WIDGET-001.md"),
        interface=_read(base / "interface" / "library.md"),
        glossary=_read(root / "specs" / "glossary.md"),
        dependency_interfaces={{}},
    )
'''


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path, log_path: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "widget.md", PRODUCT_MD)
    comp = repo_root / "specs" / "components" / "widget"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-WIDGET-001.md", ACCEPTANCE_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(repo_root / "gen" / "widget" / "widget.py", GEN_WIDGET)
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER.format(log_path=str(log_path)),
    )


def test_unauthored_generated_test_criterion_fails_not_skipped(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "assembler_calls.log"
    _build_fixture(repo_root, log_path)

    # Precondition: no cached generated test exists for the criterion.
    cached = repo_root / "verification" / "widget" / "generated-test" / "test_ac_widget_001.py"
    assert not cached.exists()

    report = verifier_orchestrator.verify("comp-widget", repo_root, test_author=None)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-WIDGET-001"]
    assert len(matching) == 1, f"expected exactly one AC-WIDGET-001 entry, got {criteria!r}"
    entry = matching[0]

    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") != "skipped"
    assert field(entry, "result") == "fail"

    assert field(report, "overall") == "fail"

    # The JSON form agrees with the attribute form.
    as_dict = report.to_dict()
    json.dumps(as_dict)
    assert as_dict["overall"] == "fail"
    dict_entry = [c for c in as_dict["criteria"] if c["id"] == "AC-WIDGET-001"][0]
    assert dict_entry["result"] == "fail"

    # Still no cached test was fabricated as a side effect of a skipped author.
    assert "test_authoring" not in dict_entry