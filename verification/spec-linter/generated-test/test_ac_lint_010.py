import json
import textwrap
from pathlib import Path

import pytest

import spec_linter


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")


COMPONENT_MD = """
---
id: comp-widget
title: Widget
status: draft
owners: [alice]
sealed: true
source_path: legacy/widget
---

# Widget

## Purpose

The widget frobs and twiddles inputs for its callers.

## Scope

- In scope: frobbing and twiddling.
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

REQ_1 = """
# R-WIDGET-001

**R-WIDGET-001** — The widget MUST frob its input.
"""

REQ_2 = """
# R-WIDGET-002

**R-WIDGET-002** — The widget MUST twiddle its input.
"""

AC_MISSING_KIND = """
# AC-WIDGET-001

Covers: R-WIDGET-001

```gherkin
Given an input value
When the widget frobs it
Then the output is frobbed
```
"""

AC_WITH_KIND = """
# AC-WIDGET-002

Covers: R-WIDGET-002
Kind: compiled

```gherkin
Given an input value
When the widget twiddles it
Then the output is twiddled
```
"""

CONSTRAINTS = """
# Constraints

- None beyond the defaults.
"""

GLOSSARY = """
# Glossary

- **Widget** — a thing that frobs.
"""


def _build_corpus(root: Path, bad_has_kind: bool = False) -> Path:
    comp = root / "specs" / "components" / "widget"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-WIDGET-001.md", REQ_1)
    _write(comp / "requirements" / "R-WIDGET-002.md", REQ_2)
    if bad_has_kind:
        _write(
            comp / "acceptance" / "AC-WIDGET-001.md",
            AC_MISSING_KIND.replace(
                "Covers: R-WIDGET-001\n", "Covers: R-WIDGET-001\nKind: compiled\n"
            ),
        )
    else:
        _write(comp / "acceptance" / "AC-WIDGET-001.md", AC_MISSING_KIND)
    _write(comp / "acceptance" / "AC-WIDGET-002.md", AC_WITH_KIND)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(root / "specs" / "glossary.md", GLOSSARY)
    return root


def _findings(report):
    findings = _get(report, "findings", None)
    if findings is None and not isinstance(report, dict):
        to_json = getattr(report, "to_json", None)
        if callable(to_json):
            data = to_json()
            if isinstance(data, str):
                data = json.loads(data)
            findings = data.get("findings")
    return list(findings or [])


def _sev(finding):
    sev = _get(finding, "severity")
    sev = getattr(sev, "value", sev)
    return str(sev).lower()


def _file(finding):
    return str(_get(finding, "file", "") or "").replace("\\", "/")


def _lint010(findings):
    return [f for f in findings if _get(f, "rule_id") == "R-LINT-010"]


def test_missing_kind_produces_fail_finding_for_r_lint_010(tmp_path):
    repo_root = _build_corpus(tmp_path)
    report = spec_linter.lint(None, repo_root)
    hits = _lint010(_findings(report))
    fails = [f for f in hits if _sev(f) == "fail"]
    assert fails, f"expected a fail-severity R-LINT-010 finding, got {hits!r}"
    assert any(_file(f).endswith("acceptance/AC-WIDGET-001.md") for f in fails), (
        f"expected the R-LINT-010 fail finding to name AC-WIDGET-001.md, got {fails!r}"
    )


def test_well_formed_criterion_is_not_flagged_by_r_lint_010(tmp_path):
    repo_root = _build_corpus(tmp_path)
    report = spec_linter.lint(None, repo_root)
    hits = _lint010(_findings(report))
    assert not any(_file(f).endswith("acceptance/AC-WIDGET-002.md") for f in hits), (
        f"well-formed AC-WIDGET-002 must not be flagged by R-LINT-010: {hits!r}"
    )


def test_hard_failures_count_reflects_r_lint_010_failure(tmp_path):
    repo_root = _build_corpus(tmp_path)
    report = spec_linter.lint(None, repo_root)
    hard = _get(report, "hard_failures", None)
    if hard is None:
        summary = _get(report, "summary", None)
        if summary is not None:
            hard = _get(summary, "hard_failures", None)
    if hard is not None:
        assert int(hard) >= 1


def test_adding_kind_removes_r_lint_010_finding(tmp_path):
    repo_root = _build_corpus(tmp_path, bad_has_kind=True)
    report = spec_linter.lint(None, repo_root)
    hits = _lint010(_findings(report))
    assert not hits, f"no R-LINT-010 findings expected once Kind: is present: {hits!r}"


def test_cli_json_reports_r_lint_010_fail_and_exits_1(tmp_path, capsys):
    repo_root = _build_corpus(tmp_path)
    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out
    assert code == 1
    data = json.loads(out)
    findings = data.get("findings", []) if isinstance(data, dict) else []
    fails = [
        f
        for f in findings
        if f.get("rule_id") == "R-LINT-010" and str(f.get("severity")).lower() == "fail"
    ]
    assert fails, f"expected a fail-severity R-LINT-010 finding in CLI JSON: {findings!r}"
    summary = data.get("summary", {})
    assert int(summary.get("hard_failures", 0)) >= 1