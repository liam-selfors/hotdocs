"""AC-LINT-009: a Covers: tag that does not resolve to a real R-id or P-id
produces a fail-severity finding for rule R-LINT-009."""

import json
from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [test-team]
sealed: true
source_path: legacy/foo/
---

# Foo

## Purpose

Foo does one small thing for the test fixture.

## Scope

- In scope: the one small thing.
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

REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — The component MUST return the input unchanged.
"""

GOOD_AC_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given an input value
When the component runs
Then it returns the input unchanged
```
"""

BAD_AC_MD = """# AC-FOO-002

Covers: R-DOES-NOT-EXIST
Kind: generated-test

```gherkin
Given an input value
When the component runs
Then it returns the input unchanged
```
"""

CONSTRAINTS_MD = """# Constraints

- None beyond the defaults. Measured by inspection.
"""

GLOSSARY_MD = """# Glossary

- **Foo** — the fixture component.
"""


def _build_repo(root: Path, include_bad: bool) -> None:
    comp = root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", GOOD_AC_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(root / "specs" / "glossary.md", GLOSSARY_MD)
    if include_bad:
        _write(comp / "acceptance" / "AC-FOO-002.md", BAD_AC_MD)


def _findings(report):
    return list(field(report, "findings"))


def _lint009_fails(findings):
    return [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-009" and field(f, "severity") == "fail"
    ]


def _hard(report):
    return report["hard_failures"] if isinstance(report, dict) else report.hard_failures


@pytest.fixture
def baseline_repo(tmp_path):
    root = tmp_path / "baseline"
    root.mkdir()
    _build_repo(root, include_bad=False)
    return root


@pytest.fixture
def bad_repo(tmp_path):
    root = tmp_path / "bad"
    root.mkdir()
    _build_repo(root, include_bad=True)
    return root


def test_baseline_has_no_r_lint_009_failure(baseline_repo):
    report = spec_linter.lint(None, baseline_repo)
    assert _lint009_fails(_findings(report)) == []


def test_dangling_covers_yields_r_lint_009_fail_finding(baseline_repo, bad_repo):
    baseline = spec_linter.lint(None, baseline_repo)
    report = spec_linter.lint(None, bad_repo)

    hits = _lint009_fails(_findings(report))
    assert len(hits) >= 1, (
        "expected a fail-severity R-LINT-009 finding, got: "
        + repr([(field(f, "rule_id"), field(f, "severity")) for f in _findings(report)])
    )

    # The dangling reference is a hard failure, counted in the summary.
    assert _hard(report) >= 1
    assert _hard(report) > _hard(baseline)
    assert _lint009_fails(_findings(baseline)) == []


def test_dangling_covers_via_cli_json_reports_failure(bad_repo, capsys):
    code = spec_linter.main(["--repo-root", str(bad_repo), "--format=json"])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    hits = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-009" and f["severity"] == "fail"
    ]
    assert len(hits) >= 1
    assert doc["summary"]["hard_failures"] >= 1