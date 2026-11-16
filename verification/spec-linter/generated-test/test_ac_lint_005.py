"""AC-LINT-005: a sealed component with no source_path gets a fail-severity
finding for rule R-LINT-005."""

import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_BODY = """
# Foo

## Purpose

Foo does a small, well-defined thing for testing the linter.

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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(root: Path, with_source_path: bool) -> Path:
    specs = root / "specs"
    comp = specs / "components" / "foo"
    fm = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [test-team]",
        "sealed: true",
    ]
    if with_source_path:
        fm.append("source_path: legacy/foo/")
        (root / "legacy" / "foo").mkdir(parents=True, exist_ok=True)
    fm.append("---")
    _write(comp / "component.md", "\n".join(fm) + "\n" + COMPONENT_BODY)
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST match existing behavior.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen foo runs\nThen foo matches existing behavior\n```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone beyond matching existing behavior.\n",
    )
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    return root


def _lint_findings(report):
    return list(field(report, "findings"))


def _r005_fails(findings):
    return [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-005" and field(f, "severity") == "fail"
    ]


def test_sealed_without_source_path_fails_r_lint_005(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", with_source_path=False)

    report = spec_linter.lint(None, repo_root)

    findings = _lint_findings(report)
    hits = _r005_fails(findings)
    assert hits, (
        "expected a fail-severity R-LINT-005 finding, got: "
        + repr([(field(f, "rule_id"), field(f, "severity")) for f in findings])
    )
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard >= 1


def test_sealed_with_source_path_has_no_r_lint_005_failure(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", with_source_path=True)

    report = spec_linter.lint(None, repo_root)

    findings = _lint_findings(report)
    assert not _r005_fails(findings), (
        "unexpected R-LINT-005 failure for sealed component carrying source_path: "
        + repr([field(f, "message") for f in _r005_fails(findings)])
    )


def test_cli_reports_r_lint_005_fail_for_sealed_without_source_path(
    tmp_path, capsys, monkeypatch
):
    repo_root = _build_repo(tmp_path / "repo", with_source_path=False)
    monkeypatch.chdir(repo_root)

    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])

    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    hits = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-005" and f["severity"] == "fail"
    ]
    assert hits, f"expected R-LINT-005 fail finding in CLI JSON output: {doc!r}"
    assert doc["summary"]["hard_failures"] >= 1