# hotdocs-criterion: sha256:8311a41ecd0daeb231c63b145c4529c2854e063100831b4a89409737c34d66c7
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(comp_id, title, source_path, rationale):
    return (
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team]\n"
        "sealed: true\n"
        "source_path: " + source_path + "\n"
        "---\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Does a small, self-contained thing for the test fixture.\n"
        "\n"
        "## Rationale\n"
        "\n"
        + rationale + "\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the fixture.\n"
        "- Out of scope: everything else.\n"
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
        "- Initial version.\n"
    )


def build_fixture(repo_root):
    specs = repo_root / "specs"

    # One real, formalized decision file so specs/decisions/ exists;
    # it cites nothing itself.
    write(
        specs / "decisions" / "D20.md",
        "---\n"
        "id: D20\n"
        "title: An unrelated decision\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "## Context\n"
        "\n"
        "Unrelated to the fixture components.\n",
    )

    # The informal brainstorm holding D1-D14, never formalized as files.
    write(
        repo_root / "notes" / "initial-ideas.md",
        "# Initial ideas\n"
        "\n"
        "## D7 - an early brainstorm idea\n"
        "\n"
        "Informal, never formalized.\n",
    )

    write(specs / "glossary.md", "# Glossary\n\n- **Fixture term** - a term.\n")

    # First component: cites a decision number with no specs/decisions/ file.
    write(
        specs / "components" / "alpha" / "component.md",
        component_md(
            "comp-alpha",
            "Alpha",
            "legacy/alpha/",
            "This design follows decision D999 exactly.",
        ),
    )

    # Second component: cites D7, one of initial-ideas.md's D1-D14.
    write(
        specs / "components" / "beta" / "component.md",
        component_md(
            "comp-beta",
            "Beta",
            "legacy/beta/",
            "This follows `notes/initial-ideas.md`'s D7, the original brainstorm idea.",
        ),
    )


def test_ac_cite_001_only_unformalized_decision_citation_is_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)

    cite_001 = [f for f in findings if field(f, "rule_id") == "R-CITE-001"]

    alpha_file = "specs/components/alpha/component.md"
    beta_file = "specs/components/beta/component.md"

    alpha_findings = [f for f in cite_001 if field(f, "file") == alpha_file]
    beta_findings = [f for f in cite_001 if field(f, "file") == beta_file]

    assert len(alpha_findings) == 1, cite_001
    assert beta_findings == [], cite_001
    assert len(cite_001) == 1, cite_001

    finding = alpha_findings[0]
    assert field(finding, "severity") in ("fail", "warn")
    assert isinstance(field(finding, "line"), int)
    assert field(finding, "line") >= 1
    assert isinstance(field(finding, "message"), str)