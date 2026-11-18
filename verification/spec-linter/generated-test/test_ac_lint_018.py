# hotdocs-criterion: sha256:fa4cf421e48e617fbb352eb0bee6a456e7a58281e1fd9909d92058c4707deed2
"""AC-LINT-018: a depends_on_guarantees entry whose owning component is not
listed in the component's own depends_on yields a fail-severity R-LINT-018
finding naming the owning component by its comp-<slug> id."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, slug, extra_frontmatter_lines):
    lines = [
        "---",
        "id: " + comp_id,
        "title: " + title,
        "status: draft",
        "owners: [test-team]",
        "sealed: true",
        "source_path: legacy/" + slug + "/",
    ]
    lines.extend(extra_frontmatter_lines)
    lines.extend(
        [
            "---",
            "",
            "# " + title,
            "",
            "## Purpose",
            "",
            "A small fixture component used for linting tests.",
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
    return "\n".join(lines)


def _requirement(req_id):
    return "\n".join(
        [
            "# " + req_id,
            "",
            "**" + req_id + "** — The component MUST behave as characterized.",
            "",
        ]
    )


def _acceptance(ac_id, req_id):
    return "\n".join(
        [
            "# " + ac_id,
            "",
            "Covers: " + req_id,
            "Kind: compiled",
            "",
            "```gherkin",
            "Given the component is loaded",
            "When it runs",
            "Then it behaves as characterized",
            "```",
            "",
        ]
    )


def _constraints():
    return "\n".join(
        [
            "# Constraints",
            "",
            "- None beyond the defaults.",
            "",
        ]
    )


def _build_component(repo_root, slug, upper, frontmatter_extra):
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        _component_md("comp-" + slug, slug.capitalize(), slug, frontmatter_extra),
    )
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    _write(base / "requirements" / (req_id + ".md"), _requirement(req_id))
    _write(base / "acceptance" / (ac_id + ".md"), _acceptance(ac_id, req_id))
    _write(base / "constraints.md", _constraints())
    return base


def _build_corpus(repo_root, foo_depends_on_bar):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a synthetic test corpus.\n",
    )
    bar = _build_component(repo_root, "bar", "BAR", [])
    _write(
        bar / "interface" / "guarantees" / "G-BAR-001.md",
        "# G-BAR-001\n\n**G-BAR-001** — Bar MUST return results in a stable order.\n",
    )
    foo_extra = ["depends_on_guarantees: [G-BAR-001]"]
    if foo_depends_on_bar:
        foo_extra.insert(0, "depends_on: [comp-bar]")
    _build_component(repo_root, "foo", "FOO", foo_extra)


def _lint_018_findings(report):
    out = []
    for finding in field(report, "findings"):
        if field(finding, "rule_id") == "R-LINT-018":
            out.append(finding)
    return out


def test_guarantee_of_undeclared_dependency_fails_naming_owner(tmp_path):
    repo_root = Path(tmp_path)
    _build_corpus(repo_root, foo_depends_on_bar=False)

    report = spec_linter.lint(None, repo_root)

    findings = _lint_018_findings(report)
    matching = [
        f
        for f in findings
        if field(f, "severity") == "fail" and "comp-bar" in str(field(f, "message"))
    ]
    assert matching, (
        "expected a fail-severity R-LINT-018 finding naming comp-bar; got: "
        + repr([(field(f, "severity"), field(f, "message")) for f in findings])
    )
    assert field(report, "hard_failures") >= 1


def test_guarantee_of_declared_dependency_has_no_missing_dependency_finding(tmp_path):
    repo_root = Path(tmp_path)
    _build_corpus(repo_root, foo_depends_on_bar=True)

    report = spec_linter.lint(None, repo_root)

    findings = _lint_018_findings(report)
    naming_bar = [f for f in findings if "comp-bar" in str(field(f, "message"))]
    assert naming_bar == [], (
        "did not expect an R-LINT-018 finding naming comp-bar when comp-bar is "
        "in depends_on; got: "
        + repr([(field(f, "severity"), field(f, "message")) for f in naming_bar])
    )