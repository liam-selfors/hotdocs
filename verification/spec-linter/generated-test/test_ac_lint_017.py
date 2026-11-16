"""AC-LINT-017: a guarantee file whose `# G-...` heading does not equal its
filename's stem produces a fail-severity finding for rule R-LINT-017."""

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
depends_on: []
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


def _build_corpus(root: Path, guarantee_heading: str) -> Path:
    specs = root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    comp = specs / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — The component MUST do the one thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven a thing\nWhen foo runs\nThen the thing is done\n```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone beyond defaults.\n",
    )
    guarantee = comp / "interface" / "guarantees" / "G-FOO-001.md"
    _write(
        guarantee,
        f"# {guarantee_heading}\n\n"
        f"**{guarantee_heading}** — The component MUST return the same "
        "result for the same input.\n",
    )
    return guarantee


def _lint017_fail_findings(report):
    findings = field(report, "findings")
    return [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-017" and field(f, "severity") == "fail"
    ]


def test_mismatched_guarantee_heading_is_a_fail_finding(tmp_path):
    _build_corpus(tmp_path, "G-FOO-002")
    report = spec_linter.lint(None, tmp_path)
    hits = _lint017_fail_findings(report)
    assert hits, (
        "expected a fail-severity R-LINT-017 finding for G-FOO-001.md "
        f"headed G-FOO-002; got {field(report, 'findings')!r}"
    )
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard >= 1


def test_matching_guarantee_heading_has_no_r_lint_017_finding(tmp_path):
    _build_corpus(tmp_path, "G-FOO-001")
    report = spec_linter.lint(None, tmp_path)
    findings = field(report, "findings")
    hits = [f for f in findings if field(f, "rule_id") == "R-LINT-017"]
    assert hits == [], f"unexpected R-LINT-017 findings: {hits!r}"


def test_cli_reports_r_lint_017_fail_and_exits_1(tmp_path, capsys):
    _build_corpus(tmp_path, "G-FOO-002")
    code = spec_linter.main(["--format=json", f"--repo-root={tmp_path}"])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    hits = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-017" and f["severity"] == "fail"
    ]
    assert hits, f"expected R-LINT-017 fail finding in CLI JSON output: {doc!r}"
    assert doc["summary"]["hard_failures"] >= 1