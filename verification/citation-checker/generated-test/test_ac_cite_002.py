import citation_checker

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


ARCH_REL = "specs/architecture/widgets.md"
REQ_GOOD_REL = "specs/components/foo/requirements/R-FOO-001.md"
REQ_BAD_REL = "specs/components/foo/requirements/R-FOO-002.md"


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n"
        "- **Widget** — a thing used only by this fixture.\n",
    )

    _write(
        repo_root / ARCH_REL,
        "---\n"
        "id: arch-widgets\n"
        "title: Widgets\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widgets\n"
        "\n"
        "## Query surface\n"
        "\n"
        "The shared views live here.\n"
        "\n"
        "## Other section\n"
        "\n"
        "Nothing else.\n",
    )

    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does a small thing for this fixture.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the small thing.\n"
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
        "- Created.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — Foo MUST read the views listed in\n"
        "`" + ARCH_REL + "`'s \"Query surface\" section.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** — Foo MUST follow the rules listed in\n"
        "`" + ARCH_REL + "`'s \"Nonexistent Heading\" section.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "When it runs\n"
        "Then it reads the views\n"
        "```\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "When it runs\n"
        "Then it follows the rules\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone.\n",
    )


def test_ac_cite_002_only_missing_heading_citation_is_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)

    cite2 = [f for f in findings if field(f, "rule_id") == "R-CITE-002"]

    # The citation to the real "Query surface" heading resolves: no finding.
    good = [f for f in cite2 if field(f, "file") == REQ_GOOD_REL]
    assert good == [], f"unexpected R-CITE-002 finding(s) for resolvable pointer: {good}"

    # The citation to "Nonexistent Heading" does not resolve: exactly one finding.
    bad = [f for f in cite2 if field(f, "file") == REQ_BAD_REL]
    assert len(bad) == 1, f"expected exactly one R-CITE-002 finding for {REQ_BAD_REL}, got {cite2}"

    # And nothing else in the corpus yields an R-CITE-002 finding.
    assert len(cite2) == 1, f"expected only the second citation flagged, got {cite2}"

    finding = bad[0]
    assert field(finding, "severity") in ("fail", "warn")
    assert isinstance(field(finding, "line"), int)
    assert isinstance(field(finding, "message"), str)