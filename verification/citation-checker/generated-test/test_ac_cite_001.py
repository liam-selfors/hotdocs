# hotdocs-criterion: sha256:8311a41ecd0daeb231c63b145c4529c2854e063100831b4a89409737c34d66c7
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug, rationale):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug.capitalize() + " component\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# " + slug.capitalize() + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "Does a small thing for the test corpus.\n"
        + "\n"
        + "## Rationale\n"
        + "\n"
        + rationale + "\n"
        + "\n"
        + "## Scope\n"
        + "\n"
        + "- In scope: the small thing.\n"
        + "- Out of scope: everything else.\n"
        + "\n"
        + "## Definitions\n"
        + "\n"
        + "None.\n"
        + "\n"
        + "## Behavior\n"
        + "\n"
        + "See `requirements/`.\n"
        + "\n"
        + "## Interfaces\n"
        + "\n"
        + "See `interface/`.\n"
        + "\n"
        + "## Data\n"
        + "\n"
        + "See `interface/data/`.\n"
        + "\n"
        + "## Acceptance criteria\n"
        + "\n"
        + "See `acceptance/`.\n"
        + "\n"
        + "## Non-functional constraints\n"
        + "\n"
        + "See `constraints.md`.\n"
        + "\n"
        + "## Open questions\n"
        + "\n"
        + "## Change log\n"
        + "\n"
        + "- Initial version.\n"
    )


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "decisions" / "D100.md",
        "---\n"
        + "id: D100\n"
        + "title: A real formal decision\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "---\n"
        + "\n"
        + "# A real formal decision\n"
        + "\n"
        + "Something was decided.\n",
    )
    write(
        repo_root / "notes" / "initial-ideas.md",
        "# Initial ideas\n\n## D7\n\nAn informal brainstorm idea.\n",
    )
    write(
        repo_root / "specs" / "components" / "alpha" / "component.md",
        component_md(
            "alpha",
            "This design follows the decision recorded in `D999`.",
        ),
    )
    write(
        repo_root / "specs" / "components" / "beta" / "component.md",
        component_md(
            "beta",
            "This design follows `notes/initial-ideas.md`'s `D7`.",
        ),
    )


def test_ac_cite_001_only_unresolved_formal_citation_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = citation_checker.check(repo_root)

    cite_findings = [f for f in findings if field(f, "rule_id") == "R-CITE-001"]
    files = [field(f, "file") for f in cite_findings]

    assert len(cite_findings) == 1, cite_findings
    assert files == ["specs/components/alpha/component.md"], cite_findings
    assert "specs/components/beta/component.md" not in files
    assert isinstance(field(cite_findings[0], "line"), int)
    assert field(cite_findings[0], "severity") in ("fail", "warn")