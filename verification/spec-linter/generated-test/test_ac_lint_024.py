# hotdocs-criterion: sha256:ed1f81b5956257305acb809f8d33bd2b576362e774f58c6a1e0722f51c9a1a2e
"""AC-LINT-024: a decision citation in a component's Purpose is an R-LINT-024 failure.

Covers: R-LINT-024
"""

from pathlib import Path

import spec_linter


CITED_TEXT = "extracted once D30 found a real coupling"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug, purpose, rationale):
    lines = [
        "---",
        "id: comp-" + slug,
        "title: " + slug.capitalize() + " Component",
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
        "sealed: true",
        "source_path: legacy/" + slug + "/",
        "---",
        "",
        "# " + slug.capitalize() + " Component",
        "",
        "## Purpose",
        "",
        purpose,
        "",
    ]
    if rationale is not None:
        lines += [
            "## Rationale",
            "",
            rationale,
            "",
        ]
    lines += [
        "## Scope",
        "",
        "- In scope: parsing widgets.",
        "- Out of scope: rendering widgets.",
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


def _build_repo(repo_root, slug, purpose, rationale):
    upper = slug.upper()
    comp_dir = repo_root / "specs" / "components" / slug
    _write(comp_dir / "component.md", _component_md(slug, purpose, rationale))
    _write(
        comp_dir / "requirements" / ("R-" + upper + "-001.md"),
        "# R-" + upper + "-001\n\n"
        "**R-" + upper + "-001** — The component MUST parse a widget.\n",
    )
    _write(
        comp_dir / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\n"
        "Covers: R-" + upper + "-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is parsed\n"
        "Then a parsed widget is returned\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n- Parsing takes under 1 second, measured by a timer.\n",
    )
    _write(
        repo_root / "specs" / "decisions" / "D30.md",
        "---\n"
        "id: D30\n"
        "title: Extract the widget parser\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n\n"
        "# D30\n\nThe widget parser is its own component.\n",
    )
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a unit of parsed input.\n",
    )
    return "specs/components/" + slug + "/component.md"


def _lint024(report):
    return [
        f for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-024"
    ]


def _norm(p):
    return str(p).replace("\\", "/")


def test_purpose_with_decision_citation_fails_r_lint_024(tmp_path):
    repo_root = tmp_path / "repo1"
    repo_root.mkdir()
    rel = _build_repo(
        repo_root,
        "foo",
        "Parses widgets for its callers; it was " + CITED_TEXT + ".",
        None,
    )

    report = spec_linter.lint(None, repo_root)
    findings = _lint024(report)
    assert findings, "expected an R-LINT-024 finding for a Purpose citing D30"
    on_file = [f for f in findings if _norm(field(f, "file")).endswith(rel)]
    assert on_file, findings
    for f in on_file:
        assert field(f, "severity") == "fail"
    assert field(report, "hard_failures") >= 1

    code = spec_linter.main(["--repo-root=" + str(repo_root)])
    assert code == 1


def test_citation_moved_to_rationale_produces_no_r_lint_024(tmp_path):
    repo_root = tmp_path / "repo2"
    repo_root.mkdir()
    _build_repo(
        repo_root,
        "bar",
        "Parses widgets for its callers.",
        "It was " + CITED_TEXT + ".",
    )

    report = spec_linter.lint(None, repo_root)
    assert _lint024(report) == []