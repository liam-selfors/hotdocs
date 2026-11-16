import json
from pathlib import Path

import pytest

import spec_linter


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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

Foo does a small, well-defined thing for testing the linter.

## Scope

- In scope: testing.
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

**R-FOO-001** — The component MUST do the small thing.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: compiled

```gherkin
Given a thing
When foo runs
Then the small thing is done
```
"""

CONSTRAINTS_MD = """# Constraints

- None beyond defaults.
"""

GLOSSARY_MD = """# Glossary

- **Thing** — a thing used in tests.
"""


def _build_repo(root: Path, guarantee_heading_id: str) -> Path:
    comp = root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(
        comp / "interface" / "guarantees" / "G-FOO-001.md",
        "# " + guarantee_heading_id + "\n\n"
        "The component MUST return results in a stable order.\n",
    )
    _write(root / "specs" / "glossary.md", GLOSSARY_MD)
    return comp / "interface" / "guarantees" / "G-FOO-001.md"


def _findings(report):
    findings = _get(report, "findings", None)
    if findings is None:
        findings = []
    return list(findings)


def _lint017_fails(report):
    out = []
    for f in _findings(report):
        if _get(f, "rule_id") == "R-LINT-017" and _get(f, "severity") == "fail":
            out.append(f)
    return out


def test_guarantee_heading_mismatch_reports_r_lint_017_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, "G-FOO-002")

    report = spec_linter.lint(None, repo_root)

    fails = _lint017_fails(report)
    assert fails, (
        "expected a fail-severity R-LINT-017 finding for G-FOO-001.md whose "
        "heading says G-FOO-002; got findings: %r" % (_findings(report),)
    )
    files = [str(_get(f, "file", "") or "") for f in fails]
    assert any("G-FOO-001" in p for p in files), (
        "expected the R-LINT-017 finding to be reported on G-FOO-001.md; "
        "got files: %r" % (files,)
    )


def test_guarantee_heading_mismatch_counts_as_hard_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, "G-FOO-002")

    report = spec_linter.lint(None, repo_root)

    hard = _get(report, "hard_failures", None)
    if hard is None and isinstance(report, dict):
        summary = report.get("summary") or {}
        hard = summary.get("hard_failures")
    assert hard is not None
    assert hard >= 1


def test_matching_guarantee_heading_has_no_r_lint_017_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, "G-FOO-001")

    report = spec_linter.lint(None, repo_root)

    fails = _lint017_fails(report)
    assert not fails, (
        "a guarantee whose heading matches its filename stem, with a unique "
        "id and an RFC 2119 keyword, must not produce an R-LINT-017 fail; "
        "got: %r" % (fails,)
    )


def test_cli_reports_r_lint_017_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, "G-FOO-002")

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])

    assert code == 1
    out = capsys.readouterr().out
    data = json.loads(out)
    findings = data.get("findings", []) if isinstance(data, dict) else []
    assert any(
        f.get("rule_id") == "R-LINT-017" and f.get("severity") == "fail"
        for f in findings
    ), "expected R-LINT-017 fail in JSON report; got %r" % (findings,)