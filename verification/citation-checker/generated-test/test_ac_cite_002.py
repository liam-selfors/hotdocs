# hotdocs-criterion: sha256:d29c5bbbf75818cab1378ec28e7fb78cadc496076d78846220760160af9c095e
"""AC-CITE-002: a section-heading pointer resolves only when the cited file
contains a heading matching the section exactly (R-CITE-002)."""

from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


ARCH_REL = "specs/architecture/graph-query-engine.md"
GOOD_REQ_REL = "specs/components/foo/requirements/R-FOO-001.md"
BAD_REQ_REL = "specs/components/foo/requirements/R-FOO-002.md"


def build_fixture(repo_root):
    write(
        repo_root / ARCH_REL,
        "---\n"
        "id: graph-query-engine\n"
        "title: Graph query engine\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Graph query engine\n"
        "\n"
        "## Overview\n"
        "\n"
        "Shared views over the corpus.\n"
        "\n"
        "## Query surface\n"
        "\n"
        "The views exposed to every consumer.\n",
    )

    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does a small thing.\n"
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
    write(
        repo_root / GOOD_REQ_REL,
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — Foo MUST read the views listed in\n"
        "`" + ARCH_REL + "`'s \"Query surface\" section.\n",
    )
    write(
        repo_root / BAD_REQ_REL,
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** — Foo MUST follow the rules in\n"
        "`" + ARCH_REL + "`'s \"Nonexistent Heading\" section.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "Foo reads the listed views.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "Foo follows the rules.\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


def test_only_unresolved_section_pointer_gets_r_cite_002_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)

    cite_002 = [f for f in findings if field(f, "rule_id") == "R-CITE-002"]

    files = [field(f, "file") for f in cite_002]
    assert GOOD_REQ_REL not in files, (
        "a pointer to an existing 'Query surface' heading must resolve: "
        + repr(cite_002)
    )
    assert len(cite_002) == 1, repr(cite_002)

    finding = cite_002[0]
    assert field(finding, "file") == BAD_REQ_REL
    assert field(finding, "severity") in ("fail", "warn")
    assert isinstance(field(finding, "line"), int)
    assert isinstance(field(finding, "message"), str)