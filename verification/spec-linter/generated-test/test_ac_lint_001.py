import json
from pathlib import Path

import pytest

import spec_linter


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _findings(report):
    findings = _get(report, "findings", None)
    if findings is None:
        return []
    return list(findings)


def _norm(path_value):
    return str(path_value).replace("\\", "/")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path, include_owners: bool) -> Path:
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\nCanonical vocabulary for this fixture corpus.\n",
    )

    comp_dir = specs / "components" / "foo"
    frontmatter_lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
    ]
    if include_owners:
        frontmatter_lines.append("owners: [fixture-team]")
    frontmatter_lines.extend(
        [
            "sealed: true",
            "source_path: legacy/foo",
            "---",
        ]
    )
    body = "\n".join(
        [
            "",
            "# Foo",
            "",
            "## Purpose",
            "",
            "Foo is a small fixture component used only to exercise the linter.",
            "",
            "## Scope",
            "",
            "- In scope: fixture behavior.",
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
    )
    component_md = comp_dir / "component.md"
    _write(component_md, "\n".join(frontmatter_lines) + "\n" + body)

    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the fixture thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "\n".join(
            [
                "# AC-FOO-001",
                "",
                "Covers: R-FOO-001",
                "Kind: compiled",
                "",
                "```gherkin",
                "Given a fixture",
                "When foo runs",
                "Then the fixture thing happens",
                "```",
                "",
            ]
        ),
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n- None beyond the fixture.\n",
    )
    return component_md


def _lint_rule_findings(report, rule_id):
    return [f for f in _findings(report) if _get(f, "rule_id") == rule_id]


def test_missing_owners_yields_fail_finding_for_r_lint_001(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, include_owners=False)

    report = spec_linter.lint(None, repo_root)

    r001 = _lint_rule_findings(report, "R-LINT-001")
    assert r001, (
        "expected at least one R-LINT-001 finding for a component.md missing "
        f"'owners'; got findings: {_findings(report)!r}"
    )

    fail_r001 = [f for f in r001 if _get(f, "severity") == "fail"]
    assert fail_r001, (
        f"expected an R-LINT-001 finding with severity 'fail'; got: {r001!r}"
    )

    on_component = [
        f
        for f in fail_r001
        if _norm(_get(f, "file", "")).endswith("components/foo/component.md")
    ]
    assert on_component, (
        "expected the fail-severity R-LINT-001 finding to be reported on "
        f"specs/components/foo/component.md; got: {fail_r001!r}"
    )

    if isinstance(report, dict):
        summary = report.get("summary") or {}
        hard_failures = summary.get("hard_failures")
    else:
        hard_failures = getattr(report, "hard_failures", None)
    assert hard_failures is not None
    assert int(hard_failures) >= 1


def test_present_owners_yields_no_r_lint_001_finding_on_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, include_owners=True)

    report = spec_linter.lint(None, repo_root)

    offending = [
        f
        for f in _lint_rule_findings(report, "R-LINT-001")
        if _get(f, "severity") == "fail"
        and _norm(_get(f, "file", "")).endswith("components/foo/component.md")
    ]
    assert not offending, (
        "a component.md carrying every required field (including 'owners') "
        f"must not produce a fail-severity R-LINT-001 finding; got: {offending!r}"
    )


def test_cli_missing_owners_exits_1_and_reports_r_lint_001(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, include_owners=False)

    exit_code = spec_linter.main(
        ["--format=json", f"--repo-root={repo_root}"]
    )
    captured = capsys.readouterr()

    assert exit_code == 1, (
        f"expected exit code 1 with a fail-severity finding; got {exit_code!r}; "
        f"stdout={captured.out!r} stderr={captured.err!r}"
    )

    payload = json.loads(captured.out)
    findings = payload.get("findings") or []
    matching = [
        f
        for f in findings
        if f.get("rule_id") == "R-LINT-001" and f.get("severity") == "fail"
    ]
    assert matching, (
        f"expected a fail-severity R-LINT-001 finding in JSON output; got: {findings!r}"
    )
    summary = payload.get("summary") or {}
    assert int(summary.get("hard_failures", 0)) >= 1