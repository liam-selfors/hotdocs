"""AC-LINT-001: a component.md with no `owners` field yields a fail-severity
R-LINT-001 finding."""

import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_BODY = """
# Foo

## Purpose

Foo does one small thing for testing.

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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(root: Path, include_owners: bool) -> Path:
    specs = root / "specs"
    lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
    ]
    if include_owners:
        lines.append("owners: [test-team]")
    lines += [
        "sealed: true",
        "source_path: legacy/foo/",
        "---",
    ]
    _write(
        specs / "components" / "foo" / "component.md",
        "\n".join(lines) + "\n" + COMPONENT_BODY,
    )
    _write(
        specs / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST match existing behavior.\n",
    )
    _write(
        specs / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it matches existing behavior\n```\n",
    )
    _write(
        specs / "components" / "foo" / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    return root


def _findings(report):
    return list(field(report, "findings"))


def _lint001_fail_on_foo(findings):
    out = []
    for f in findings:
        if field(f, "rule_id") != "R-LINT-001":
            continue
        if field(f, "severity") != "fail":
            continue
        file = str(field(f, "file")).replace("\\", "/")
        if file.endswith("specs/components/foo/component.md"):
            out.append(f)
    return out


def test_control_with_owners_has_no_r_lint_001_finding(tmp_path):
    repo = _build_repo(tmp_path / "ok", include_owners=True)
    report = spec_linter.lint(None, repo)
    lint001 = [
        f
        for f in _findings(report)
        if field(f, "rule_id") == "R-LINT-001" and field(f, "severity") == "fail"
    ]
    assert lint001 == [], f"unexpected R-LINT-001 findings: {lint001!r}"


def test_missing_owners_yields_fail_finding_for_r_lint_001(tmp_path):
    repo = _build_repo(tmp_path / "bad", include_owners=False)
    report = spec_linter.lint(None, repo)
    findings = _findings(report)
    matching = _lint001_fail_on_foo(findings)
    assert matching, (
        "expected a fail-severity R-LINT-001 finding on "
        f"specs/components/foo/component.md, got: {findings!r}"
    )
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard >= 1


def test_cli_missing_owners_reports_r_lint_001_and_exits_1(tmp_path, capsys):
    repo = _build_repo(tmp_path / "cli", include_owners=False)
    code = spec_linter.main(["--format=json", f"--repo-root={repo}"])
    captured = capsys.readouterr()
    assert code == 1
    doc = json.loads(captured.out)
    matching = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-001"
        and f["severity"] == "fail"
        and str(f["file"]).replace("\\", "/").endswith(
            "specs/components/foo/component.md"
        )
    ]
    assert matching, f"no fail R-LINT-001 finding in JSON report: {doc!r}"
    assert doc["summary"]["hard_failures"] >= 1