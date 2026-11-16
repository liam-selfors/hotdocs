"""AC-CITE-002 (covers R-CITE-002).

Given a live requirement citing a real file's "Query surface" section,
  and another citing the same file's "Nonexistent Heading" section
When check(repo_root) runs
Then only the second citation gets a R-CITE-002 finding
"""

from pathlib import Path

import citation_checker


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


ARCH_REL = "specs/architecture/graph-query-engine.md"
GOOD_REQ_REL = "specs/components/foo/requirements/R-FOO-001.md"
BAD_REQ_REL = "specs/components/foo/requirements/R-FOO-002.md"


def _build_fixture(repo_root: Path) -> None:
    # Glossary (no frontmatter).
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary.\n"
        "\n"
        "- **Widget** — a small test thing.\n",
    )

    # The real file whose section is cited.
    _write(
        repo_root / ARCH_REL,
        "---\n"
        "id: graph-query-engine\n"
        "title: Graph query engine\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "---\n"
        "\n"
        "# Graph query engine\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Exposes shared views over the corpus.\n"
        "\n"
        "## Query surface\n"
        "\n"
        "The views every consumer reads.\n",
    )

    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: fixture behavior.\n"
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
        repo_root / GOOD_REQ_REL,
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — The component MUST read only the views listed in "
        "`specs/architecture/graph-query-engine.md`'s \"Query surface\" section.\n",
    )
    _write(
        repo_root / BAD_REQ_REL,
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** — The component MUST follow the rules in "
        "`specs/architecture/graph-query-engine.md`'s \"Nonexistent Heading\" section.\n",
    )

    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: llm-judge\n"
        "\n"
        "The component reads only listed views.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: llm-judge\n"
        "\n"
        "The component follows the rules.\n",
    )

    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


def _norm(path_value) -> str:
    return str(path_value).replace("\\", "/")


def test_only_unresolved_section_pointer_gets_r_cite_002(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = citation_checker.check(repo_root)

    assert isinstance(findings, list)

    cite2 = [f for f in findings if _get(f, "rule_id") == "R-CITE-002"]
    cite2_files = [_norm(_get(f, "file")) for f in cite2]

    # The resolving pointer ("Query surface") must produce no R-CITE-002 finding.
    assert GOOD_REQ_REL not in cite2_files, (
        f"Resolving 'Query surface' pointer was flagged: {cite2!r}"
    )

    # The dangling pointer ("Nonexistent Heading") must produce exactly one.
    assert cite2_files.count(BAD_REQ_REL) == 1, (
        f"Expected exactly one R-CITE-002 finding on {BAD_REQ_REL}, got: {cite2!r}"
    )

    # And nothing else anywhere gets an R-CITE-002 finding.
    assert len(cite2) == 1, f"Unexpected extra R-CITE-002 findings: {cite2!r}"

    finding = cite2[0]
    severity = _get(finding, "severity")
    assert severity in ("fail", "warn")
    line = _get(finding, "line")
    assert isinstance(line, int) and not isinstance(line, bool)
    assert line >= 1
    message = _get(finding, "message")
    assert isinstance(message, str) and message


def test_findings_have_exact_documented_keys(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = citation_checker.check(repo_root)

    cite2 = [f for f in findings if _get(f, "rule_id") == "R-CITE-002"]
    assert len(cite2) == 1
    finding = cite2[0]
    if isinstance(finding, dict):
        assert set(finding.keys()) == {"rule_id", "severity", "file", "line", "message"}
    else:
        for key in ("rule_id", "severity", "file", "line", "message"):
            assert hasattr(finding, key)