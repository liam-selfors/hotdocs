# hotdocs-criterion: sha256:19d1a84fd017087bce62b846790baf93980a6d449aaee5ebd075b0ee1cccfe33
"""AC-LINT-001: a component.md with no `owners` field in its frontmatter
yields a fail-severity finding for rule R-LINT-001 (covers R-LINT-001)."""

import json
from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(include_owners):
    lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
    ]
    if include_owners:
        lines.append("owners: [pipeline-team]")
    lines += [
        "sealed: true",
        "source_path: legacy/foo/",
        "---",
        "",
        "# Foo",
        "",
        "## Purpose",
        "",
        "Foo does one small thing for testing the linter.",
        "",
        "## Scope",
        "",
        "- In scope: the one small thing.",
        "- Out of scope: everything else.",
        "",
        "## Definitions",
        "",
        "None.",
        "",
        "## Behavior",
        "",
        "See `requirements/`.",
        "",
        "## Interfaces",
        "",
        "See `interface/`.",
        "",
        "## Data",
        "",
        "See `interface/data/`.",
        "",
        "## Acceptance criteria",
        "",
        "See `acceptance/`.",
        "",
        "## Non-functional constraints",
        "",
        "See `constraints.md`.",
        "",
        "## Open questions",
        "",
        "## Change log",
        "",
        "- Initial draft.",
        "",
    ]
    return "\n".join(lines)


def _build_fixture(repo_root, include_owners):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    _write(comp / "component.md", _component_md(include_owners))
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 Foo MUST do the one small thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it does the one small thing\n```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone beyond the defaults.\n",
    )
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test component.\n",
    )
    return comp / "component.md"


def _is_component_md(file_value):
    text = str(file_value).replace("\\", "/")
    return text.endswith("specs/components/foo/component.md") or text.endswith(
        "components/foo/component.md"
    )


def _r_lint_001_fail_findings(findings):
    out = []
    for f in findings:
        if field(f, "rule_id") == "R-LINT-001" and field(f, "severity") == "fail":
            out.append(f)
    return out


def test_missing_owners_reports_fail_finding_for_r_lint_001(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, include_owners=False)

    report = spec_linter.lint(None, repo_root)

    findings = list(field(report, "findings"))
    hits = _r_lint_001_fail_findings(findings)
    assert hits, "expected a fail-severity R-LINT-001 finding, got: " + repr(findings)
    assert any(_is_component_md(field(f, "file")) for f in hits), (
        "expected the R-LINT-001 finding to be reported on component.md, got: "
        + repr(hits)
    )
    assert field(report, "hard_failures") >= 1


def test_owners_present_has_no_r_lint_001_fail_on_component_md(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, include_owners=True)

    report = spec_linter.lint(None, repo_root)

    findings = list(field(report, "findings"))
    hits = [
        f
        for f in _r_lint_001_fail_findings(findings)
        if _is_component_md(field(f, "file"))
    ]
    assert hits == [], "unexpected R-LINT-001 finding(s): " + repr(hits)


def test_cli_json_reports_r_lint_001_fail_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, include_owners=False)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    captured = capsys.readouterr()

    assert code == 1
    doc = json.loads(captured.out)
    hits = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-001" and f["severity"] == "fail"
    ]
    assert hits, "expected a fail-severity R-LINT-001 finding in JSON: " + captured.out
    assert any(_is_component_md(f["file"]) for f in hits)
    assert doc["summary"]["hard_failures"] >= 1