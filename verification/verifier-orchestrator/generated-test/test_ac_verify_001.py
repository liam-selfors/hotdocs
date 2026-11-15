import verifier_orchestrator

from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = """---
id: comp-widget
title: Widget
status: draft
owners: [team-a]
depends_on: []
realizes: [P-WIDGET]
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

PRODUCT_MD = """---
id: P-WIDGET
title: Widgets
status: draft
owners: [team-a]
---

# Widgets

## Purpose

Widgets double numbers.

## Scope

- In scope: doubling numbers.

### CS-WIDGET-001

Covers: P-WIDGET
Kind: compiled

```gherkin
Given a value is 2
When double is invoked with [value]
Then result equals 4
```
"""

GLOSSARY_MD = """# Glossary

- **Widget** — a test term.
"""

REQUIREMENT_MD = """# R-WIDGET-001

**R-WIDGET-001** — `double(x)` MUST return `2 * x`.
"""

ACCEPTANCE_MD = """# AC-WIDGET-001

Covers: R-WIDGET-001
Kind: compiled

```gherkin
Given a value is 2
When double is invoked with [value]
Then result equals 4
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

WIDGET_PY = """def double(x):
    return 2 * x
"""


FAKE_COMPILER_TEMPLATE = '''import dataclasses
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

GATE_VERSION = "criterion-compiler@1.0.0"

_LOG_PATH = {log_path!r}

_SOURCE = {source!r}


def _log(line):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\\n")


@dataclasses.dataclass
class ParsedCriterion:
    criterion_id: str = ""
    covers: str = ""
    kind: str = ""
    gherkin: str = ""
    file: Any = None


@dataclasses.dataclass
class InterfaceSurface:
    functions: Dict[str, Any] = dataclasses.field(default_factory=dict)
    types: Dict[str, Any] = dataclasses.field(default_factory=dict)
    module_name: str = ""


@dataclasses.dataclass
class CompileReport:
    outputs: List[Dict[str, Any]] = dataclasses.field(default_factory=list)
    gate_version: str = GATE_VERSION
    summary: Dict[str, Any] = dataclasses.field(default_factory=dict)


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def compile_criterion(criterion, surface=None):
    _log("compile_criterion " + str(_get(criterion, "criterion_id")))
    return {{"status": "compiled", "source": _SOURCE}}


def _parse_acceptance(text):
    covers = None
    kind = None
    for line in text.splitlines():
        stripped = line.strip()
        if covers is None and stripped.startswith("Covers:"):
            covers = stripped[len("Covers:"):].strip()
        elif covers is not None and kind is None and stripped.startswith("Kind:"):
            kind = stripped[len("Kind:"):].strip()
    return covers, kind


def compile(component_id, repo_root, target="pytest", out_dir=None):
    _log("compile " + str(component_id))
    repo_root = Path(repo_root)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    if out_dir is None:
        out_dir = repo_root / "verification" / slug / "compiled"
    out_dir = Path(out_dir)
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    skipped = 0
    acc_dir = repo_root / "specs" / "components" / slug / "acceptance"
    for acc in sorted(acc_dir.glob("AC-*.md")):
        criterion_id = acc.stem
        covers, kind = _parse_acceptance(acc.read_text(encoding="utf-8"))
        if kind != "compiled":
            skipped += 1
            continue
        _log("compile_for " + criterion_id)
        name = "test_" + criterion_id.lower().replace("-", "_") + ".py"
        dest = out_dir / name
        dest.write_text(_SOURCE, encoding="utf-8")
        try:
            rel = str(dest.resolve().relative_to(repo_root.resolve()))
        except ValueError:
            rel = str(dest.resolve())
        outputs.append({{
            "criterion_id": criterion_id,
            "covers": covers,
            "status": "compiled",
            "file": rel,
        }})
    return CompileReport(
        outputs=outputs,
        gate_version=GATE_VERSION,
        summary={{
            "compiled": len(outputs),
            "errors": 0,
            "skipped_non_compiled_kind": skipped,
        }},
    )
'''


def _emitted_source(expected):
    return (
        "import widget\n"
        "\n"
        "\n"
        "def test_ac_widget_001():\n"
        "    result = widget.double(2)\n"
        "    assert result == %d\n" % expected
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root, log_path, expected):
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    _write(repo_root / "specs" / "product" / "widgets.md", PRODUCT_MD)
    comp = repo_root / "specs" / "components" / "widget"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-WIDGET-001.md", ACCEPTANCE_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(repo_root / "gen" / "widget" / "widget.py", WIDGET_PY)
    fake = FAKE_COMPILER_TEMPLATE.format(
        log_path=str(log_path), source=_emitted_source(expected)
    )
    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        fake,
    )


@pytest.mark.parametrize(
    "expected_value, expected_result",
    [(4, "pass"), (5, "fail")],
)
def test_compiled_criterion_dispatches_to_compiler_and_reports_result(
    tmp_path, expected_value, expected_result
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "compiler_calls.log"
    _build_fixture(repo_root, log_path, expected_value)

    report = verifier_orchestrator.verify("comp-widget", repo_root)

    # The mock compiler was invoked for that criterion.
    assert log_path.is_file(), "mock criterion-compiler was never invoked"
    lines = [l.strip() for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert lines, "mock criterion-compiler was never invoked"
    invoked_for_criterion = any(
        l == "compile_criterion AC-WIDGET-001"
        or l == "compile_for AC-WIDGET-001"
        or l == "compile comp-widget"
        for l in lines
    )
    assert invoked_for_criterion, lines

    # Its pass/fail result appears in the report under that criterion's id.
    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-WIDGET-001"]
    assert len(matching) == 1, criteria
    entry = matching[0]
    assert field(entry, "result") == expected_result, entry