"""AC-LINT-010: an acceptance criterion missing its `Kind:` tag yields a
fail-severity R-LINT-010 finding when `hotdocs lint` runs against it."""

import json
from pathlib import Path

import spec_linter


AC_REL = "specs/components/foo/acceptance/AC-FOO-001.md"


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

- In scope: the one thing.
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

**R-FOO-001** — Foo MUST do the one thing.
"""

GHERKIN = """```gherkin
Given a foo input
When foo runs
Then foo does the one thing
```
"""


def _ac_text(with_kind: bool) -> str:
    kind_line = "Kind: compiled\n" if with_kind else ""
    return "# AC-FOO-001\n\nCovers: R-FOO-001\n" + kind_line + "\n" + GHERKIN


def _build_repo(root: Path, with_kind: bool) -> Path:
    comp = root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", _ac_text(with_kind))
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — the fixture component.\n",
    )
    return root


def _is_ac_file(file_value) -> bool:
    return str(file_value).replace("\\", "/").endswith(AC_REL)


def _lint_findings(repo_root: Path):
    report = spec_linter.lint(None, repo_root)
    return report, list(field(report, "findings"))


def test_missing_kind_yields_fail_finding_for_r_lint_010(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", with_kind=False)
    report, findings = _lint_findings(repo_root)

    matches = [
        f for f in findings
        if field(f, "rule_id") == "R-LINT-010" and field(f, "severity") == "fail"
    ]
    assert matches, (
        "expected a fail-severity R-LINT-010 finding, got: "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "file"))
                for f in findings])
    )
    assert any(_is_ac_file(field(f, "file")) for f in matches), (
        "R-LINT-010 finding should point at the criterion missing its Kind: "
        + repr([field(f, "file") for f in matches])
    )
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard >= 1


def test_criterion_with_kind_has_no_r_lint_010_finding(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", with_kind=True)
    _, findings = _lint_findings(repo_root)

    offending = [
        f for f in findings
        if field(f, "rule_id") == "R-LINT-010" and _is_ac_file(field(f, "file"))
    ]
    assert offending == [], (
        "a complete criterion with Kind: and Given/When/Then must not trip "
        "R-LINT-010: " + repr([field(f, "message") for f in offending])
    )


def test_cli_reports_r_lint_010_fail_and_exits_1(tmp_path, capsys):
    repo_root = _build_repo(tmp_path / "repo", with_kind=False)

    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    matches = [
        f for f in doc["findings"]
        if f["rule_id"] == "R-LINT-010" and f["severity"] == "fail"
    ]
    assert matches, "expected a fail-severity R-LINT-010 finding in JSON report"
    assert any(_is_ac_file(f["file"]) for f in matches)
    assert doc["summary"]["hard_failures"] >= 1