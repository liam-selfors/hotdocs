import json
from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = """---
id: comp-foo
title: Foo Widget
status: draft
owners: [test-team]
sealed: true
source_path: legacy/foo/
---

# Foo Widget

## Purpose

Counts widgets for a caller.

## Scope

- In scope: counting widgets.
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

# Control requirement: carries an RFC 2119 keyword.
REQ_WITH_KEYWORD = """# R-FOO-001

**R-FOO-001** \u2014 The widget counter MUST return the number of widgets held.
"""

# Requirement under test: no RFC 2119 keyword anywhere in its text.
REQ_WITHOUT_KEYWORD = """# R-FOO-002

**R-FOO-002** \u2014 The widget counter returns zero when it holds no widgets.
"""

AC_1 = """# AC-FOO-001

Covers: R-FOO-001
Kind: compiled

```gherkin
Given a counter holding 3 widgets
When the count is read
Then the result is 3
```
"""

AC_2 = """# AC-FOO-002

Covers: R-FOO-002
Kind: compiled

```gherkin
Given a counter holding 0 widgets
When the count is read
Then the result is 0
```
"""

CONSTRAINTS = """# Constraints

- Counting completes in under 1 second, measured by a wall-clock timer.
"""

GLOSSARY = """# Glossary

- **Widget** \u2014 a thing being counted.
"""


def _build_repo(root: Path) -> Path:
    specs = root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(REQ_WITH_KEYWORD)
    (comp / "requirements" / "R-FOO-002.md").write_text(REQ_WITHOUT_KEYWORD)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(AC_1)
    (comp / "acceptance" / "AC-FOO-002.md").write_text(AC_2)
    (comp / "constraints.md").write_text(CONSTRAINTS)
    (specs / "glossary.md").write_text(GLOSSARY)
    return root


def _findings(report):
    return list(field(report, "findings"))


def _r_lint_007_for(findings, req_stem):
    out = []
    for f in findings:
        if field(f, "rule_id") != "R-LINT-007":
            continue
        if req_stem in str(field(f, "file")):
            out.append(f)
    return out


def test_requirement_without_rfc2119_keyword_fails_r_lint_007(tmp_path):
    repo_root = _build_repo(tmp_path)

    report = spec_linter.lint(None, repo_root)
    findings = _findings(report)

    missing = _r_lint_007_for(findings, "R-FOO-002")
    assert missing, (
        "expected an R-LINT-007 finding for the keyword-less requirement; got: "
        + repr([(field(f, "rule_id"), field(f, "file"), field(f, "message")) for f in findings])
    )
    assert any(field(f, "severity") == "fail" for f in missing), (
        "R-LINT-007 finding must be fail-severity; got: "
        + repr([field(f, "severity") for f in missing])
    )

    # The finding is reported against the offending requirement file.
    fail_files = [str(field(f, "file")) for f in missing if field(f, "severity") == "fail"]
    assert any(p.replace("\\", "/").endswith("requirements/R-FOO-002.md") for p in fail_files)

    # A hard failure is counted.
    hard = report["summary"]["hard_failures"] if isinstance(report, dict) and "summary" in report \
        else field(report, "hard_failures")
    assert hard >= 1

    # Control: the requirement that does carry an RFC 2119 keyword (and a
    # well-formed id matching its filename) gets no R-LINT-007 finding.
    assert _r_lint_007_for(findings, "R-FOO-001") == []


def test_cli_lint_reports_r_lint_007_fail_and_exits_1(tmp_path, capsys):
    repo_root = _build_repo(tmp_path)

    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])
    captured = capsys.readouterr()

    assert code == 1
    doc = json.loads(captured.out)
    findings = doc["findings"]
    hits = [
        f for f in findings
        if f["rule_id"] == "R-LINT-007"
        and "R-FOO-002" in str(f["file"])
        and f["severity"] == "fail"
    ]
    assert hits, repr(findings)
    assert doc["summary"]["hard_failures"] >= 1