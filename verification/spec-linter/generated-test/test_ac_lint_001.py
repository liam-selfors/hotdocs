# hotdocs-criterion: sha256:4d0cca507829c7a65ea7aa875ecb307c8681a378c397bdf51b01ba3c46466617
"""AC-LINT-001: a component.md with no `owners` field in its frontmatter
yields a fail-severity finding for rule R-LINT-001."""

import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root, with_owners):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a small thing used in tests.\n",
    )
    comp_dir = specs / "components" / "foo"
    frontmatter_lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
    ]
    if with_owners:
        frontmatter_lines.append("owners: [test-team]")
    frontmatter_lines += [
        "depends_on: []",
        "sealed: true",
        "source_path: legacy/foo/",
        "---",
    ]
    body = (
        "\n".join(frontmatter_lines)
        + "\n\n# Foo\n\n"
        + "## Purpose\n\nFoo does a small thing for tests.\n\n"
        + "## Scope\n\n- In scope: the small thing.\n- Out of scope: everything else.\n\n"
        + "## Definitions\n\nNone.\n\n"
        + "## Behavior\n\nSee `requirements/`.\n\n"
        + "## Interfaces\n\nSee `interface/`.\n\n"
        + "## Data\n\nSee `interface/data/`.\n\n"
        + "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        + "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        + "## Open questions\n\n"
        + "## Change log\n\n- Initial draft.\n"
    )
    _write(comp_dir / "component.md", body)
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the small thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a foo\n"
        "When it runs\n"
        "Then it does the small thing\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n- None beyond defaults.\n",
    )


def _lint_001_fail_findings(report):
    out = []
    for finding in field(report, "findings"):
        if (
            str(field(finding, "rule_id")) == "R-LINT-001"
            and str(field(finding, "severity")) == "fail"
        ):
            out.append(finding)
    return out


def test_missing_owners_yields_r_lint_001_fail(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, with_owners=False)

    report = spec_linter.lint(None, repo_root)

    matches = _lint_001_fail_findings(report)
    assert matches, "expected a fail-severity R-LINT-001 finding, got: " + repr(
        field(report, "findings")
    )
    files = [str(field(f, "file")).replace("\\", "/") for f in matches]
    assert any(f.endswith("specs/components/foo/component.md") for f in files), files
    assert field(report, "hard_failures") >= 1


def test_present_owners_yields_no_r_lint_001_finding(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, with_owners=True)

    report = spec_linter.lint(None, repo_root)

    for finding in field(report, "findings"):
        if str(field(finding, "rule_id")) == "R-LINT-001":
            file_ = str(field(finding, "file")).replace("\\", "/")
            assert not file_.endswith("specs/components/foo/component.md"), repr(finding)


def test_cli_reports_r_lint_001_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, with_owners=False)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    captured = capsys.readouterr()

    assert code == 1
    doc = json.loads(captured.out)
    matches = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-001" and f["severity"] == "fail"
    ]
    assert matches, captured.out
    assert any(
        str(f["file"]).replace("\\", "/").endswith("specs/components/foo/component.md")
        for f in matches
    )
    assert doc["summary"]["hard_failures"] >= 1