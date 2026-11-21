# hotdocs-criterion: sha256:01168adc2b19ef8b7a83819c9d273321b6db37476dcbd87b3ac40cd7894af5ae
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug, purpose, rationale=None):
    text = (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose + "\n"
        "\n"
    )
    if rationale is not None:
        text += "## Rationale\n\n" + rationale + "\n\n"
    text += (
        "## Scope\n"
        "\n"
        "- In scope: parsing widget files.\n"
        "- Out of scope: writing widget files.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )
    return text


def build_component(repo_root, slug, purpose, rationale=None):
    upper = slug.upper()
    comp_dir = repo_root / "specs" / "components" / slug
    write(comp_dir / "component.md", component_md(slug, purpose, rationale))
    write(
        comp_dir / "requirements" / ("R-" + upper + "-001.md"),
        "# R-" + upper + "-001\n\n"
        "**R-" + upper + "-001** — The component MUST parse each widget file "
        "into one record.\n",
    )
    write(
        comp_dir / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\n"
        "Covers: R-" + upper + "-001\n"
        "Kind: compiled\n\n"
        "```gherkin\n"
        "Given a widget file\n"
        "When the component parses it\n"
        "Then it returns one record\n"
        "```\n",
    )
    write(
        comp_dir / "constraints.md",
        "# Constraints\n\n- Parses a widget file in under 1 second, measured by a timer.\n",
    )
    return "specs/components/" + slug + "/component.md"


def build_base(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a file the component parses.\n",
    )
    write(
        repo_root / "specs" / "decisions" / "D30.md",
        "---\n"
        "id: D30\n"
        "title: Extract widget parsing\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# D30\n"
        "\n"
        "Widget parsing is extracted into its own component.\n",
    )


def lint_findings(repo_root):
    report = spec_linter.lint(None, repo_root)
    return report, list(field(report, "findings"))


def r024(findings):
    return [f for f in findings if field(f, "rule_id") == "R-LINT-024"]


def test_purpose_with_decision_citation_fails_and_rationale_citation_does_not(tmp_path):
    # Component whose Purpose cites D30.
    bad_root = tmp_path / "bad"
    build_base(bad_root)
    bad_file = build_component(
        bad_root,
        "alpha",
        "Alpha parses widget files into records. It was extracted once D30 found a real coupling.",
    )
    report, findings = lint_findings(bad_root)
    bad = r024(findings)
    assert bad, "expected an R-LINT-024 finding for a Purpose citing D30"
    assert any(
        field(f, "severity") == "fail"
        and str(field(f, "file")).replace("\\", "/").endswith(bad_file)
        for f in bad
    ), bad
    assert all(field(f, "severity") == "fail" for f in bad)
    assert field(report, "hard_failures") >= 1

    # Component whose Purpose is clean, with the citation moved to Rationale.
    good_root = tmp_path / "good"
    build_base(good_root)
    good_file = build_component(
        good_root,
        "beta",
        "Beta parses widget files into records.",
        rationale="Beta was extracted once D30 found a real coupling.",
    )
    _, good_findings = lint_findings(good_root)
    good = r024(good_findings)
    assert good == [], good
    assert not any(
        str(field(f, "file")).replace("\\", "/").endswith(good_file)
        and field(f, "rule_id") == "R-LINT-024"
        for f in good_findings
    )