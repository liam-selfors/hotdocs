# hotdocs-criterion: sha256:fc8621cc68af2557976001fa737f1a5ae525894b5806c636f8868bb55862908b
import json
from pathlib import Path

import pytest

import spec_linter


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [alice]
sealed: true
source_path: legacy/foo
---

# Foo

## Purpose

Foo does a small, self-contained thing for test purposes.

## Scope

- In scope: the foo behavior.
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

R_FOO_001 = """# R-FOO-001

**R-FOO-001** — Foo MUST return the input unchanged.
"""

R_FOO_002 = """# R-FOO-002

**R-FOO-002** — Foo MUST NOT modify any file on disk.
"""

AC_FOO_001_COVERS_002 = """# AC-FOO-001

Covers: R-FOO-002
Kind: generated-test

```gherkin
Given any input
When foo runs
Then no file on disk is modified
```
"""

AC_FOO_002_COVERS_001 = """# AC-FOO-002

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given an input value
When foo runs
Then it returns the same value
```
"""

CONSTRAINTS_MD = """# Constraints

- Foo MUST complete within 1 second, measured by wall-clock timing.
"""

GLOSSARY_MD = """# Glossary

- **Foo** — a test-only fixture term.
"""


def _build_repo(root: Path, cover_r_foo_001: bool) -> Path:
    specs = root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(R_FOO_001)
    (comp / "requirements" / "R-FOO-002.md").write_text(R_FOO_002)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(AC_FOO_001_COVERS_002)
    if cover_r_foo_001:
        (comp / "acceptance" / "AC-FOO-002.md").write_text(AC_FOO_002_COVERS_001)
    (comp / "constraints.md").write_text(CONSTRAINTS_MD)
    (specs / "glossary.md").write_text(GLOSSARY_MD)
    return root


def _names(finding, req_id):
    message = _get(finding, "message") or ""
    file_ = _get(finding, "file") or ""
    return req_id in str(message) or req_id in str(file_)


def _lint008(findings):
    return [f for f in findings if _get(f, "rule_id") == "R-LINT-008"]


def test_uncovered_requirement_yields_fail_finding(tmp_path):
    repo_root = _build_repo(tmp_path, cover_r_foo_001=False)
    report = spec_linter.lint(None, repo_root)
    findings = list(_get(report, "findings") or [])
    lint008 = _lint008(findings)
    matching = [
        f for f in lint008
        if _get(f, "severity") == "fail" and _names(f, "R-FOO-001")
    ]
    assert matching, (
        "expected a fail-severity R-LINT-008 finding naming R-FOO-001, got: %r"
        % (findings,)
    )

    if isinstance(report, dict):
        hard = (report.get("summary") or {}).get("hard_failures")
    else:
        hard = getattr(report, "hard_failures", None)
    assert hard is not None and hard >= 1


def test_covered_requirement_not_flagged(tmp_path):
    repo_root = _build_repo(tmp_path, cover_r_foo_001=False)
    report = spec_linter.lint(None, repo_root)
    findings = list(_get(report, "findings") or [])
    for f in _lint008(findings):
        assert not _names(f, "R-FOO-002"), (
            "R-FOO-002 is covered by AC-FOO-001 and must not be flagged: %r" % (f,)
        )


def test_adding_coverage_clears_finding(tmp_path):
    repo_root = _build_repo(tmp_path, cover_r_foo_001=True)
    report = spec_linter.lint(None, repo_root)
    findings = list(_get(report, "findings") or [])
    flagged = [f for f in _lint008(findings) if _names(f, "R-FOO-001")]
    assert not flagged, (
        "R-FOO-001 is covered by AC-FOO-002; no R-LINT-008 finding expected: %r"
        % (flagged,)
    )


def test_cli_json_reports_finding_and_exits_1(tmp_path, capsys):
    repo_root = _build_repo(tmp_path, cover_r_foo_001=False)
    code = spec_linter.main(["--format=json", "--repo-root=%s" % repo_root])
    out = capsys.readouterr().out
    assert code == 1
    data = json.loads(out)
    findings = data.get("findings", [])
    matching = [
        f for f in findings
        if f.get("rule_id") == "R-LINT-008"
        and f.get("severity") == "fail"
        and ("R-FOO-001" in str(f.get("message", "")) or "R-FOO-001" in str(f.get("file", "")))
    ]
    assert matching, "expected R-LINT-008 fail finding naming R-FOO-001 in JSON: %r" % (findings,)
    assert data.get("summary", {}).get("hard_failures", 0) >= 1