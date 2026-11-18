# hotdocs-criterion: sha256:64eba2eeba5325607c2e47f3b215a9fc4bd156ba5b225a9216b611f46af7d964
"""AC-LINT-018b: a depends_on_guarantees entry that does not resolve to an
existing guarantee id yields a fail-severity R-LINT-018 finding."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(extra_frontmatter_lines):
    lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [team-a]",
        "sealed: true",
        "source_path: legacy/foo/",
    ]
    lines.extend(extra_frontmatter_lines)
    lines.append("---")
    lines.extend(
        [
            "",
            "# Foo",
            "",
            "## Purpose",
            "",
            "Foo does a small thing for testing.",
            "",
            "## Scope",
            "",
            "- In scope: the small thing.",
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
    return "\n".join(lines)


def _build_corpus(repo_root: Path, extra_frontmatter_lines) -> Path:
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Foo thing** — a thing foo does.\n",
    )
    comp = specs / "components" / "foo"
    _write(comp / "component.md", _component_md(extra_frontmatter_lines))
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the small thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it does the small thing\n```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone beyond the defaults.\n",
    )
    return comp / "component.md"


def _r018_fail_findings(report):
    findings = field(report, "findings")
    return [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-018" and field(f, "severity") == "fail"
    ]


def test_unresolved_depends_on_guarantee_is_r_lint_018_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, ["depends_on_guarantees: [G-DOES-NOT-EXIST]"])

    report = spec_linter.lint(None, repo_root)

    matches = _r018_fail_findings(report)
    assert matches, (
        "expected a fail-severity R-LINT-018 finding, got: "
        + repr(
            [
                (field(f, "rule_id"), field(f, "severity"), field(f, "message"))
                for f in field(report, "findings")
            ]
        )
    )
    # The finding is a hard failure, so the report counts at least one.
    assert field(report, "hard_failures") >= 1
    # The finding is reported against the offending component's file.
    assert any(
        "specs/components/foo/component.md" in str(field(f, "file")).replace("\\", "/")
        for f in matches
    )


def test_no_r_lint_018_fail_without_the_bad_entry(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, [])

    report = spec_linter.lint(None, repo_root)

    assert _r018_fail_findings(report) == []