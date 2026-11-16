"""AC-LINT-008 / R-LINT-008: forward traceability.

Given a requirement R-FOO-001 with zero acceptance criteria whose Covers:
tag names it, when hotdocs lint runs against the component, then the report
contains a fail-severity finding for rule R-LINT-008 naming R-FOO-001.
"""

import json
from pathlib import Path

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

Foo does a small, well-defined thing for testing the linter.

## Scope

- In scope: doing the thing.
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

CONSTRAINTS_MD = """# Constraints

- Latency: the thing MUST complete within 1 second, measured by a timer.
"""

R_FOO_001 = """# R-FOO-001

**R-FOO-001** — Foo MUST return the input string unchanged.
"""

R_FOO_002 = """# R-FOO-002

**R-FOO-002** — Foo MUST return an empty string for empty input.
"""


def _ac_foo_001(extra_prose: str = "") -> str:
    return (
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given an empty input string\n"
        "When foo runs\n"
        "Then the result is an empty string\n"
        "```\n" + extra_prose
    )


GLOSSARY_MD = """# Glossary

- **Thing** — the unit of work foo performs.
"""


def build_fixture(root: Path, extra_ac_prose: str = "") -> Path:
    comp = root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(comp / "requirements" / "R-FOO-001.md", R_FOO_001)
    _write(comp / "requirements" / "R-FOO-002.md", R_FOO_002)
    _write(comp / "acceptance" / "AC-FOO-001.md", _ac_foo_001(extra_ac_prose))
    _write(root / "specs" / "glossary.md", GLOSSARY_MD)
    return root


def _names(finding, req_id: str) -> bool:
    message = str(field(finding, "message") or "")
    file = str(field(finding, "file") or "")
    return req_id in message or req_id in file


def _lint_008_findings(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "rule_id") == "R-LINT-008"]


def test_uncovered_requirement_yields_fail_finding_for_r_lint_008(tmp_path):
    repo_root = build_fixture(tmp_path)

    report = spec_linter.lint(None, repo_root)

    lint_008 = _lint_008_findings(report)
    naming = [
        f
        for f in lint_008
        if field(f, "severity") == "fail" and _names(f, "R-FOO-001")
    ]
    assert naming, (
        "expected a fail-severity R-LINT-008 finding naming R-FOO-001, got: "
        f"{[(field(f, 'rule_id'), field(f, 'severity'), field(f, 'file'), field(f, 'message')) for f in field(report, 'findings')]}"
    )

    # Negative control: the covered requirement R-FOO-002 is not reported.
    assert not any(_names(f, "R-FOO-002") for f in lint_008), (
        f"R-FOO-002 is covered by AC-FOO-001 but was reported: {lint_008}"
    )

    # A fail finding means the report counts at least one hard failure.
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard >= 1


def test_later_covers_prose_does_not_count_as_coverage(tmp_path):
    # Only the first `Covers:` in an acceptance file is its tag; a later
    # mention is prose and does not cover R-FOO-001.
    repo_root = build_fixture(
        tmp_path,
        extra_ac_prose="\nUnrelated note, for example: Covers: R-FOO-001\n",
    )

    report = spec_linter.lint(None, repo_root)

    lint_008 = _lint_008_findings(report)
    assert any(
        field(f, "severity") == "fail" and _names(f, "R-FOO-001") for f in lint_008
    ), f"expected R-LINT-008 fail naming R-FOO-001, got: {lint_008}"


def test_fully_covered_component_has_no_r_lint_008_finding(tmp_path):
    repo_root = build_fixture(tmp_path)
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given the input string \"abc\"\n"
        "When foo runs\n"
        "Then the result is \"abc\"\n"
        "```\n",
    )

    report = spec_linter.lint(None, repo_root)

    lint_008 = _lint_008_findings(report)
    assert not [f for f in lint_008 if field(f, "severity") == "fail"], (
        f"no requirement is uncovered, yet R-LINT-008 fired: {lint_008}"
    )


def test_cli_reports_r_lint_008_and_exits_1(tmp_path, capsys):
    repo_root = build_fixture(tmp_path)

    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])

    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    findings = doc["findings"]
    assert any(
        f["rule_id"] == "R-LINT-008"
        and f["severity"] == "fail"
        and ("R-FOO-001" in str(f.get("message", "")) or "R-FOO-001" in str(f.get("file", "")))
        for f in findings
    ), f"expected R-LINT-008 fail naming R-FOO-001 in JSON report, got: {findings}"
    assert doc["summary"]["hard_failures"] >= 1