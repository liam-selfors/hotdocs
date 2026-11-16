"""AC-LINT-024 (Covers: R-LINT-024).

Given a component's Purpose section containing the text "extracted once
D30 found a real coupling", when the linter runs, then it fails with
R-LINT-024; a second component whose Purpose has no decision citation
(the same citation moved to its own Rationale section instead) produces
no R-LINT-024 finding.
"""

import json
from pathlib import Path

import spec_linter


CITING_TEXT = "extracted once D30 found a real coupling"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug: str, purpose: str, rationale) -> str:
    parts = [
        "---",
        f"id: comp-{slug}",
        f"title: {slug.replace('-', ' ').title()}",
        "status: draft",
        "owners: [test-team]",
        "sealed: true",
        f"source_path: legacy/{slug}/",
        "---",
        "",
        f"# {slug}",
        "",
        "## Purpose",
        "",
        purpose,
        "",
    ]
    if rationale is not None:
        parts += ["## Rationale", "", rationale, ""]
    parts += [
        "## Scope",
        "",
        "- In scope: transforming widgets.",
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
    return "\n".join(parts)


def _add_component(root: Path, slug: str, prefix: str, purpose: str, rationale) -> None:
    base = root / "specs" / "components" / slug
    _write(base / "component.md", _component_md(slug, purpose, rationale))
    _write(
        base / "requirements" / f"R-{prefix}-001.md",
        f"# R-{prefix}-001\n\n**R-{prefix}-001** — The component MUST "
        "return the widget unchanged when given a widget.\n",
    )
    _write(
        base / "acceptance" / f"AC-{prefix}-001.md",
        f"# AC-{prefix}-001\n\nCovers: R-{prefix}-001\nKind: compiled\n\n"
        "```gherkin\nGiven a widget\nWhen the component runs\n"
        "Then it returns the widget unchanged\n```\n",
    )
    _write(
        base / "constraints.md",
        "# Constraints\n\n- Completes in under 1 second, measured by a timer.\n",
    )


def _base_repo(root: Path) -> None:
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a thing the component transforms.\n",
    )
    _write(
        root / "specs" / "decisions" / "D30.md",
        "---\nid: D30\ntitle: Extract widget handling\nstatus: draft\n"
        "owners: [test-team]\n---\n\n# D30\n\nA real coupling was found.\n",
    )


def _bad_purpose() -> str:
    return (
        "Transforms widgets for its dependents; it was "
        + CITING_TEXT
        + " between widget parsing and widget rendering."
    )


def _good_purpose() -> str:
    return "Transforms widgets for its dependents, returning each one unchanged."


def _good_rationale() -> str:
    return "This component was " + CITING_TEXT + " between parsing and rendering."


def _findings(report):
    return list(field(report, "findings"))


def _lint024(report):
    return [f for f in _findings(report) if field(f, "rule_id") == "R-LINT-024"]


def _norm(p) -> str:
    return str(p).replace("\\", "/")


def test_purpose_with_decision_citation_fails_with_r_lint_024(tmp_path):
    root = tmp_path / "repo"
    _base_repo(root)
    _add_component(root, "bad-widget", "BADW", _bad_purpose(), None)

    report = spec_linter.lint(None, root)
    hits = _lint024(report)
    assert hits, f"expected an R-LINT-024 finding, got {_findings(report)!r}"
    assert any(field(f, "severity") == "fail" for f in hits), hits
    assert any(
        _norm(field(f, "file")).endswith("specs/components/bad-widget/component.md")
        for f in hits
    ), hits
    assert field(report, "hard_failures") >= 1


def test_purpose_citation_cli_exits_1_and_reports_r_lint_024(tmp_path, capsys):
    root = tmp_path / "repo"
    _base_repo(root)
    _add_component(root, "bad-widget", "BADW", _bad_purpose(), None)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(root)])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    hits = [f for f in doc["findings"] if f["rule_id"] == "R-LINT-024"]
    assert hits
    assert any(f["severity"] == "fail" for f in hits)


def test_citation_moved_to_rationale_produces_no_r_lint_024(tmp_path):
    root = tmp_path / "repo"
    _base_repo(root)
    _add_component(root, "good-widget", "GOODW", _good_purpose(), _good_rationale())

    report = spec_linter.lint(None, root)
    assert _lint024(report) == [], _lint024(report)


def test_mixed_corpus_flags_only_the_purpose_citing_component(tmp_path):
    root = tmp_path / "repo"
    _base_repo(root)
    _add_component(root, "bad-widget", "BADW", _bad_purpose(), None)
    _add_component(root, "good-widget", "GOODW", _good_purpose(), _good_rationale())

    report = spec_linter.lint(None, root)
    hits = _lint024(report)
    assert any(
        field(f, "severity") == "fail"
        and _norm(field(f, "file")).endswith("specs/components/bad-widget/component.md")
        for f in hits
    ), hits
    assert not any("good-widget" in _norm(field(f, "file")) for f in hits), hits
    assert field(report, "hard_failures") >= 1