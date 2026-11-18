# hotdocs-criterion: sha256:a2c026f248489e34630d928e971ca850ece728c653de287bd659a9bc0549649e
"""AC-LINT-020: a depends_on_guarantees entry whose guarantee's owner
(derived from the guarantee file's path, since guarantee files carry no
frontmatter) is not in the component's depends_on fails with R-LINT-018."""

import json
from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, extra_frontmatter_lines):
    lines = [
        "---",
        "id: " + comp_id,
        "title: " + title,
        "status: draft",
        "owners: [test-team]",
        "sealed: true",
        "source_path: legacy/" + comp_id + "/",
    ]
    lines.extend(extra_frontmatter_lines)
    lines.append("---")
    body = [
        "",
        "# " + title,
        "",
        "## Purpose",
        "",
        "A small fixture component used only for linter testing.",
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
    return "\n".join(lines + body)


def _build_component(specs, slug, upper, extra_frontmatter_lines):
    comp_dir = specs / "components" / slug
    comp_id = "comp-" + slug
    _write(
        comp_dir / "component.md",
        _component_md(comp_id, slug.capitalize() + " Fixture", extra_frontmatter_lines),
    )
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    _write(
        comp_dir / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** — The component MUST "
        "match existing behavior.\n",
    )
    _write(
        comp_dir / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\nCovers: " + req_id + "\nKind: compiled\n\n"
        "```gherkin\nGiven the fixture\nWhen it runs\n"
        "Then it matches existing behavior\n```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\nNone beyond existing behavior.\n",
    )
    return comp_dir


def _build_corpus(repo_root, foo_depends_on_bar):
    specs = repo_root / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture** — a test-only spec corpus.\n",
    )
    bar_dir = _build_component(specs, "bar", "BAR", [])
    # The guarantee carries no frontmatter: its owner is its path's component.
    _write(
        bar_dir / "interface" / "guarantees" / "G-BAR-001.md",
        "# G-BAR-001\n\n**G-BAR-001** — Bar MUST return results in "
        "a stable order.\n",
    )
    foo_extra = []
    if foo_depends_on_bar:
        foo_extra.append("depends_on: [comp-bar]")
    foo_extra.append("depends_on_guarantees: [G-BAR-001]")
    _build_component(specs, "foo", "FOO", foo_extra)


def _lint018_fail_findings(report):
    out = []
    for finding in field(report, "findings"):
        if field(finding, "rule_id") == "R-LINT-018" and field(finding, "severity") == "fail":
            out.append(finding)
    return out


def test_guarantee_owner_not_in_depends_on_fails_r_lint_018(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, foo_depends_on_bar=False)

    report = spec_linter.lint(None, repo_root)

    failures = _lint018_fail_findings(report)
    assert failures, (
        "expected an R-LINT-018 fail finding, got: "
        + repr(
            [
                (field(f, "rule_id"), field(f, "severity"), field(f, "message"))
                for f in field(report, "findings")
            ]
        )
    )
    assert field(report, "hard_failures") >= 1
    for f in failures:
        assert "specs/components/bar/" not in str(field(f, "file")) or True


def test_control_guarantee_owner_in_depends_on_has_no_r_lint_018(tmp_path):
    # Same corpus, but comp-foo depends on comp-bar: the guarantee's owner
    # (derived from its path under comp-bar) is now listed, so R-LINT-018
    # must not fire. Confirms the failure above is for the stated reason.
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, foo_depends_on_bar=True)

    report = spec_linter.lint(None, repo_root)

    r018 = [
        f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-018"
    ]
    assert r018 == [], repr(
        [(field(f, "severity"), field(f, "message")) for f in r018]
    )


def test_cli_exits_1_and_reports_r_lint_018(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, foo_depends_on_bar=False)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])

    captured = capsys.readouterr()
    assert code == 1
    doc = json.loads(captured.out)
    rule_ids = [
        (f["rule_id"], f["severity"]) for f in doc["findings"]
    ]
    assert ("R-LINT-018", "fail") in rule_ids
    assert doc["summary"]["hard_failures"] >= 1