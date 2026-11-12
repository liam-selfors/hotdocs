"""AC-CITE-001 (covers R-CITE-001).

Given a live component.md citing a decision number with no corresponding
specs/decisions/ file, and a second citing D7, one of D1-D14, never
formalized as files, when check(repo_root) runs, then only the first
citation gets a R-CITE-001 finding.
"""

from pathlib import Path

import citation_checker


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug: str, rationale: str) -> str:
    return (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} component\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "---\n"
        "\n"
        f"# {slug.capitalize()}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"The {slug} component matches existing behavior; do not regenerate.\n"
        "\n"
        "## Rationale\n"
        "\n"
        f"{rationale}\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: existing behavior.\n"
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


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a thing used in this fixture.\n",
    )
    # One real, formalized decision record, so specs/decisions/ exists and
    # is non-empty; neither D500 nor D7 has a file here.
    _write(
        repo_root / "specs" / "decisions" / "D100.md",
        "---\n"
        "id: D100\n"
        "title: A real formal decision\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "---\n"
        "\n"
        "# A real formal decision\n"
        "\n"
        "Something was decided.\n",
    )
    _write(
        repo_root / "notes" / "initial-ideas.md",
        "# Initial ideas\n\n- D7 — an informal brainstorm decision.\n",
    )
    # First live component: cites a decision number with no file.
    _write(
        repo_root / "specs" / "components" / "alpha" / "component.md",
        _component_md(
            "alpha",
            "This design follows `D500`, which was never written down.",
        ),
    )
    # Second live component: cites D7, one of D1-D14, never formalized.
    _write(
        repo_root / "specs" / "components" / "beta" / "component.md",
        _component_md(
            "beta",
            "This design follows `D7` from `notes/initial-ideas.md`.",
        ),
    )


def _norm(p) -> str:
    return str(p).replace("\\", "/") if p is not None else ""


def test_ac_cite_001_only_unformalized_non_d1_d14_citation_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)

    cite_001 = [f for f in findings if _field(f, "rule_id") == "R-CITE-001"]

    alpha_rel = "specs/components/alpha/component.md"
    beta_rel = "specs/components/beta/component.md"

    alpha_findings = [f for f in cite_001 if _norm(_field(f, "file")) == alpha_rel]
    beta_findings = [f for f in cite_001 if _norm(_field(f, "file")) == beta_rel]

    assert len(alpha_findings) == 1, (
        f"expected exactly one R-CITE-001 finding for {alpha_rel}, got {cite_001!r}"
    )
    assert beta_findings == [], (
        f"expected no R-CITE-001 finding for the D7 citation in {beta_rel}, "
        f"got {beta_findings!r}"
    )
    assert len(cite_001) == 1, (
        f"expected exactly one R-CITE-001 finding overall, got {cite_001!r}"
    )

    finding = alpha_findings[0]
    assert _field(finding, "severity") in ("fail", "warn")
    line = _field(finding, "line")
    assert isinstance(line, int) and not isinstance(line, bool)
    assert line >= 1
    message = _field(finding, "message")
    assert isinstance(message, str) and message