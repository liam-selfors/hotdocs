# hotdocs-criterion: sha256:b064c9d1c9a05946abc95dbeed6c058f9a270b05004024bc94a013a54ccf97cd
"""AC-LINT-001: a component.md with no `owners` field in its frontmatter
produces a fail-severity finding for rule R-LINT-001."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _severity(finding):
    sev = field(finding, "severity")
    return getattr(sev, "value", sev)


def _norm(path_value):
    return str(path_value).replace("\\", "/")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root, include_owners):
    frontmatter_lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
    ]
    if include_owners:
        frontmatter_lines.append("owners: [pipeline-team]")
    frontmatter_lines.extend(
        [
            "sealed: true",
            "source_path: legacy/foo/",
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
            "Foo does a small, well-defined thing for testing.",
            "",
            "## Scope",
            "",
            "- In scope: foo.",
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
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(comp_dir / "component.md", "\n".join(frontmatter_lines) + "\n" + body)
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — The component MUST do foo.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen foo runs\nThen foo happens\n```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\nNone beyond the defaults.\n",
    )
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    return comp_dir / "component.md"


def _r_lint_001_fails_for(report, rel_file):
    findings = field(report, "findings")
    result = []
    for f in findings:
        if field(f, "rule_id") != "R-LINT-001":
            continue
        if _severity(f) != "fail":
            continue
        if _norm(field(f, "file")).endswith(rel_file):
            result.append(f)
    return result


def test_missing_owners_is_fail_finding_for_r_lint_001(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, include_owners=False)

    report = spec_linter.lint(None, repo_root)

    hits = _r_lint_001_fails_for(report, "specs/components/foo/component.md")
    assert hits, (
        "expected a fail-severity R-LINT-001 finding for component.md, got: "
        + repr(field(report, "findings"))
    )
    assert field(report, "hard_failures") >= 1


def test_owners_present_gives_no_r_lint_001_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, include_owners=True)

    report = spec_linter.lint(None, repo_root)

    hits = _r_lint_001_fails_for(report, "specs/components/foo/component.md")
    assert not hits, (
        "did not expect an R-LINT-001 fail finding when owners is present, got: "
        + repr(hits)
    )


def test_missing_owners_cli_exit_code_is_one(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, include_owners=False)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    capsys.readouterr()

    assert code == 1