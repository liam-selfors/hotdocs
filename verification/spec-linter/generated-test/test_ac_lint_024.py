# hotdocs-criterion: sha256:59e999dd9104751b1065f3be1bc68cc6c61f79774abe723c7f5177e13e4d0be1
"""AC-LINT-024: a component's Purpose section citing a decision id fails
with R-LINT-024; the same citation moved into Rationale produces no
R-LINT-024 finding."""

from pathlib import Path

import pytest

import spec_linter


CITATION_TEXT = "extracted once D30 found a real coupling"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug, purpose_text, rationale_text):
    lines = [
        "---",
        "id: comp-" + slug,
        "title: " + slug.capitalize() + " Component",
        "status: draft",
        "owners: [pipeline-team]",
        "sealed: true",
        "source_path: legacy/" + slug + "/",
        "---",
        "",
        "# " + slug.capitalize() + " Component",
        "",
        "## Purpose",
        "",
        purpose_text,
        "",
    ]
    if rationale_text is not None:
        lines += [
            "## Rationale",
            "",
            rationale_text,
            "",
        ]
    lines += [
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
    return "\n".join(lines)


def _write_component(repo_root, slug, upper, purpose_text, rationale_text):
    base = repo_root / "specs" / "components" / slug
    _write(base / "component.md", _component_md(slug, purpose_text, rationale_text))
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    _write(
        base / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** — The component MUST "
        "transform each widget it is given.\n",
    )
    _write(
        base / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\nCovers: " + req_id + "\nKind: compiled\n\n"
        "```gherkin\nGiven a widget\nWhen the component runs\n"
        "Then the widget is transformed\n```\n",
    )
    _write(
        base / "constraints.md",
        "# Constraints\n\n- Latency: under 1 second per widget, measured "
        "by a timing test.\n",
    )
    return "specs/components/" + slug + "/component.md"


def _write_decision(repo_root):
    _write(
        repo_root / "specs" / "decisions" / "D30.md",
        "---\nid: D30\ntitle: Extract the coupling\nstatus: draft\n"
        "owners: [pipeline-team]\n---\n\n# D30\n\nA real coupling was "
        "found, so the unit was extracted.\n",
    )


def _write_glossary(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a unit of work the fixture "
        "components transform.\n",
    )


def _norm(path_value):
    return str(path_value).replace("\\", "/")


def _lint024_findings_for(report, rel_file):
    findings = field(report, "findings")
    out = []
    for f in findings:
        if field(f, "rule_id") != "R-LINT-024":
            continue
        fpath = _norm(field(f, "file"))
        if fpath == rel_file or fpath.endswith("/" + rel_file) or fpath.endswith(rel_file):
            out.append(f)
    return out


def _all_lint024(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-024"]


@pytest.mark.parametrize(
    "purpose_citation",
    [
        CITATION_TEXT,
        "extracted once `D30` found a real coupling",
    ],
)
def test_purpose_citation_fails_and_rationale_citation_does_not(tmp_path, purpose_citation):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_glossary(repo_root)
    _write_decision(repo_root)

    bad_file = _write_component(
        repo_root,
        "alpha",
        "ALPHA",
        "Transforms widgets for downstream consumers; " + purpose_citation + ".",
        None,
    )
    good_file = _write_component(
        repo_root,
        "beta",
        "BETA",
        "Transforms widgets for downstream consumers.",
        "This component was " + CITATION_TEXT + ".",
    )

    report = spec_linter.lint(None, repo_root)

    bad = _lint024_findings_for(report, bad_file)
    assert bad, "expected an R-LINT-024 finding for the Purpose citation, got: " + repr(
        [(field(f, "rule_id"), _norm(field(f, "file"))) for f in field(report, "findings")]
    )
    for f in bad:
        assert field(f, "severity") == "fail"

    assert field(report, "hard_failures") >= 1

    good = _lint024_findings_for(report, good_file)
    assert good == [], "Rationale citation must not produce R-LINT-024: " + repr(
        [field(f, "message") for f in good]
    )


def test_rationale_only_corpus_has_no_lint024_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_glossary(repo_root)
    _write_decision(repo_root)

    _write_component(
        repo_root,
        "beta",
        "BETA",
        "Transforms widgets for downstream consumers.",
        "This component was " + CITATION_TEXT + ".",
    )

    report = spec_linter.lint(None, repo_root)

    assert _all_lint024(report) == [], repr(
        [(_norm(field(f, "file")), field(f, "message")) for f in _all_lint024(report)]
    )


def test_purpose_only_corpus_fails_with_lint024(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_glossary(repo_root)
    _write_decision(repo_root)

    bad_file = _write_component(
        repo_root,
        "alpha",
        "ALPHA",
        "Transforms widgets for downstream consumers; " + CITATION_TEXT + ".",
        None,
    )

    report = spec_linter.lint(None, repo_root)

    bad = _lint024_findings_for(report, bad_file)
    assert len(bad) >= 1
    assert all(field(f, "severity") == "fail" for f in bad)
    assert field(report, "hard_failures") >= 1