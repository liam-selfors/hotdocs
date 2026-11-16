"""AC-CITE-005 (Covers: R-CITE-005).

Given a decision record's builds_on naming a decision number with no
corresponding specs/decisions/ file, and a second record's builds_on
naming D7, one of D1-D14, never formalized as files,
When check(repo_root) runs,
Then only the first gets an R-CITE-005 finding.
"""

from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _decision(doc_id: str, builds_on: str) -> str:
    return (
        "---\n"
        f"id: {doc_id}\n"
        f"title: Decision {doc_id}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        f"builds_on: {builds_on}\n"
        "---\n"
        f"# {doc_id}\n"
        "\n"
        "A synthetic decision record used as a test fixture.\n"
    )


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Fixture term** — a term used only by this test fixture.\n",
    )
    # First record: builds_on a decision number that has no file at all.
    _write(
        repo_root / "specs" / "decisions" / "D300.md",
        _decision("D300", "[D500]"),
    )
    # Second record: builds_on D7, one of the informal D1-D14, never
    # formalized as files -- exempt from resolution.
    _write(
        repo_root / "specs" / "decisions" / "D301.md",
        _decision("D301", "[D7]"),
    )


def test_ac_cite_005_only_unresolved_builds_on_is_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    # Preconditions of the fixture itself.
    assert (repo_root / "specs" / "decisions" / "D300.md").is_file()
    assert (repo_root / "specs" / "decisions" / "D301.md").is_file()
    assert not (repo_root / "specs" / "decisions" / "D500.md").exists()
    assert not (repo_root / "specs" / "decisions" / "D7.md").exists()

    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)

    cite5 = [f for f in findings if field(f, "rule_id") == "R-CITE-005"]

    # Exactly one R-CITE-005 finding: for the first record only.
    assert len(cite5) == 1, f"expected exactly one R-CITE-005 finding, got {cite5!r}"

    finding = cite5[0]
    assert field(finding, "file") == "specs/decisions/D300.md"
    assert field(finding, "severity") in ("fail", "warn")
    line = field(finding, "line")
    assert isinstance(line, int) and not isinstance(line, bool)
    assert line >= 1
    assert isinstance(field(finding, "message"), str)

    # The D7 record never gets an R-CITE-005 finding.
    assert not any(
        field(f, "file") == "specs/decisions/D301.md" for f in cite5
    )