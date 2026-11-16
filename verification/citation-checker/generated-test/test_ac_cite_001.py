import citation_checker

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root: Path, slug: str, upper: str, rationale: str) -> None:
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} component\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
        f"# {slug.capitalize()}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Does the {slug} thing for its callers.\n"
        "\n"
        "## Rationale\n"
        "\n"
        f"{rationale}\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the thing.\n"
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
        "- Initial version.\n",
    )
    _write(
        base / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n"
        "\n"
        f"**R-{upper}-001** — The component MUST do the thing.\n",
    )
    _write(
        base / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given an input\n"
        "When the thing runs\n"
        "Then the thing is done\n"
        "```\n",
    )
    _write(
        base / "constraints.md",
        "# Constraints\n"
        "\n"
        "- Runs quickly. Measured by timing a call.\n",
    )


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** — a small thing.\n",
    )
    # One real, formal decision file exists; neither cited number has one.
    _write(
        repo_root / "specs" / "decisions" / "D20.md",
        "---\n"
        "id: D20\n"
        "title: Some formal decision\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "# D20\n"
        "\n"
        "A formal decision.\n",
    )
    # First: cites a decision number with no specs/decisions/ file.
    _component(
        repo_root,
        "alpha",
        "ALPHA",
        "This design follows `D998`.",
    )
    # Second: cites D7, one of D1-D14, never formalized as a file.
    _component(
        repo_root,
        "beta",
        "BETA",
        "This design follows `D7`.",
    )


def test_ac_cite_001_only_unresolved_formal_citation_gets_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    assert not (repo_root / "specs" / "decisions" / "D998.md").exists()
    assert not (repo_root / "specs" / "decisions" / "D7.md").exists()

    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)

    cite_001 = [f for f in findings if field(f, "rule_id") == "R-CITE-001"]

    alpha_file = "specs/components/alpha/component.md"
    beta_file = "specs/components/beta/component.md"

    alpha_findings = [f for f in cite_001 if field(f, "file") == alpha_file]
    beta_findings = [f for f in cite_001 if field(f, "file") == beta_file]

    # Only the first citation gets an R-CITE-001 finding.
    assert len(alpha_findings) == 1, cite_001
    assert beta_findings == [], cite_001
    assert len(cite_001) == 1, cite_001

    finding = alpha_findings[0]
    assert field(finding, "severity") in ("fail", "warn")
    line = field(finding, "line")
    assert isinstance(line, int)
    assert line >= 1
    assert isinstance(field(finding, "message"), str)